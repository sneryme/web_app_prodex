"""Бизнес-логика маршрута участника: вход по коду, согласия, автоопределение этапа, ответы.

Держим её отдельно от views.py, чтобы её можно было тестировать без DRF и переиспользовать
(например, из будущего Celery-таска подсчёта completion для employer dashboard).
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from apps.assessments.models import AnswerResponse, Question, QuestionnaireVersion
from apps.assessments.scoring import compute_scores_for_stage
from apps.organizations.models import Organization, Stream

from .models import ConsentRecord, ParticipantToken, StageProgress

# Порядок методик в едином маршруте участника (ТЗ FR-05.1). Пока не подтверждён методологом —
# зафиксирован здесь, а не выведен из алфавита/id, чтобы порядок не менялся случайно.
QUESTIONNAIRE_ORDER = [QuestionnaireVersion.CODE_EQ5D, QuestionnaireVersion.CODE_STAI, QuestionnaireVersion.CODE_HADS]


class EntryCodeInvalid(Exception):
    """Ссылка/QR не распознаны — ТЗ FR-01.4: токен при этом не создаётся."""


class SessionNotFound(Exception):
    """Токен не найден. Отдаём 404 без уточнений, чтобы не дать способ перебора токенов."""


class ConsentRequired(Exception):
    """Попытка сохранить ответ без действующего согласия на обработку ПД (ТЗ FR-03.3)."""


class NoActiveStage(Exception):
    """Оба этапа завершены, либо активные методики ещё не подключены методологом."""


class UnknownQuestion(Exception):
    """question_id/option_id не относятся к активному набору вопросов текущего этапа."""


def active_questions() -> list[Question]:
    """Единый порядок вопросов для входного и итогового тестирования (ТЗ FR-05.1)."""
    order = {code: index for index, code in enumerate(QUESTIONNAIRE_ORDER)}
    versions = list(QuestionnaireVersion.objects.filter(is_active=True))
    versions.sort(key=lambda version: order.get(version.code, len(order)))
    questions: list[Question] = []
    for version in versions:
        questions.extend(version.questions.prefetch_related("options").order_by("order"))
    return questions


def create_session(entry_code: str) -> ParticipantToken:
    try:
        organization = Organization.objects.get(entry_code=entry_code)
    except Organization.DoesNotExist as exc:
        raise EntryCodeInvalid from exc

    # Если у клиента ровно один активный поток — привязываем участника к нему автоматически.
    # Несколько одновременных активных потоков или их отсутствие — участник остаётся без потока,
    # координатор сможет назначить его позже (открытый вопрос, см. README «Важные ограничения»).
    stream = Stream.objects.filter(organization=organization, status=Stream.STATUS_ACTIVE).first()

    token = ParticipantToken.objects.create(organization=organization, stream=stream)
    StageProgress.objects.create(token=token, stage=StageProgress.STAGE_BASELINE)
    return token


def get_token(token_value: str) -> ParticipantToken:
    try:
        return ParticipantToken.objects.get(token=token_value)
    except ParticipantToken.DoesNotExist as exc:
        raise SessionNotFound from exc


def consent_status(token: ParticipantToken) -> str:
    """"required" | "granted" | "declined" — считаем по последнему согласию на обработку ПД."""
    latest = (
        ConsentRecord.objects.filter(token=token, consent_type=ConsentRecord.TYPE_DATA_PROCESSING)
        .order_by("-accepted_at")
        .first()
    )
    if latest is None:
        return "required"
    return "granted" if latest.accepted else "declined"


def record_consent(token: ParticipantToken, consent_type: str, text_version: str, accepted: bool) -> ConsentRecord:
    return ConsentRecord.objects.create(
        token=token, consent_type=consent_type, text_version=text_version, accepted=accepted
    )


def current_stage(token: ParticipantToken) -> Optional[str]:
    """Система сама определяет этап — ручного выбора «первичный/вторичный» нет (ТЗ FR-04)."""
    total = len(active_questions())
    if total == 0:
        return None
    baseline_answered = AnswerResponse.objects.filter(token=token, stage=StageProgress.STAGE_BASELINE).count()
    if baseline_answered < total:
        return StageProgress.STAGE_BASELINE
    followup_answered = AnswerResponse.objects.filter(token=token, stage=StageProgress.STAGE_FOLLOWUP).count()
    if followup_answered < total:
        return StageProgress.STAGE_FOLLOWUP
    return None


def _sync_stage_progress(token: ParticipantToken) -> None:
    """StageProgress — производный кэш для будущей аналитики completion (FR-09), не источник истины."""
    total = len(active_questions())
    for stage in (StageProgress.STAGE_BASELINE, StageProgress.STAGE_FOLLOWUP):
        answered = AnswerResponse.objects.filter(token=token, stage=stage).count()
        if answered == 0:
            status = StageProgress.STATUS_NOT_STARTED
        elif total and answered >= total:
            status = StageProgress.STATUS_COMPLETED
        else:
            status = StageProgress.STATUS_IN_PROGRESS

        progress, _ = StageProgress.objects.get_or_create(token=token, stage=stage)
        if progress.status != status:
            progress.status = status
            if status == StageProgress.STATUS_IN_PROGRESS and not progress.started_at:
                progress.started_at = timezone.now()
            if status == StageProgress.STATUS_COMPLETED and not progress.completed_at:
                progress.completed_at = timezone.now()
            progress.save()


def session_state(token: ParticipantToken) -> dict:
    """Полное состояние сессии для фронтенда: какой экран показать и что в нём отрисовать."""
    consent = consent_status(token)
    stage = current_stage(token)
    questions = active_questions()

    # ТЗ FR-03.3/FR-03.1: до согласия участнику не должен быть доступен даже контент вопросов,
    # не только сохранение ответов.
    show_questions = stage is not None and consent == "granted"

    answers_by_question = {}
    if show_questions:
        answers_by_question = {
            answer.question_id: answer
            for answer in AnswerResponse.objects.filter(token=token, stage=stage)
        }

    question_payload = []
    if show_questions:
        for question in questions:
            answer = answers_by_question.get(question.id)
            question_payload.append(
                {
                    "id": question.id,
                    "code": question.code,
                    "text": question.text,
                    "indicator_code": question.indicator_code,
                    "options": [
                        {"id": option.id, "value": option.value, "label": option.label}
                        for option in question.options.all()
                    ],
                    "answer": (
                        {"option_id": answer.selected_option_id, "raw_value": answer.raw_value}
                        if answer is not None
                        else None
                    ),
                }
            )

    answered_count = sum(1 for item in question_payload if item["answer"] is not None)
    return {
        "token": token.token,
        "consent_status": consent,
        "stage": stage,
        "questions": question_payload,
        "progress": {"answered": answered_count, "total": len(questions)},
    }


def submit_answer(
    token: ParticipantToken, question_id: int, option_id: Optional[int], raw_value: str
) -> dict:
    """Идемпотентное сохранение ответа (ТЗ FR-06.6): повторная отправка того же вопроса — не дубль, а апдейт."""
    if consent_status(token) != "granted":
        raise ConsentRequired

    stage = current_stage(token)
    if stage is None:
        raise NoActiveStage

    questions_by_id = {question.id: question for question in active_questions()}
    question = questions_by_id.get(question_id)
    if question is None:
        raise UnknownQuestion

    selected_option = None
    if option_id is not None:
        selected_option = next((o for o in question.options.all() if o.id == option_id), None)
        if selected_option is None:
            raise UnknownQuestion

    AnswerResponse.objects.update_or_create(
        token=token,
        stage=stage,
        question=question,
        defaults={"selected_option": selected_option, "raw_value": raw_value},
    )
    _sync_stage_progress(token)
    _maybe_score_stage(token, stage)
    return session_state(token)


def _maybe_score_stage(token: ParticipantToken, stage: str) -> None:
    """ТЗ FR-07: scoring запускается автоматически, как только этап полностью отвечен."""
    total = len(active_questions())
    answered = AnswerResponse.objects.filter(token=token, stage=stage).count()
    if total and answered >= total:
        compute_scores_for_stage(token, stage)
