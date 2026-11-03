"""Бизнес-логика маршрута участника: вход по коду, согласия, автоопределение этапа, ответы.

Держим её отдельно от views.py, чтобы её можно было тестировать без DRF и переиспользовать
(например, из будущего Celery-таска подсчёта completion для employer dashboard).
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from apps.assessments.models import AnswerResponse, Question, QuestionnaireVersion, TestBundle
from apps.assessments.scoring import compute_scores_for_stage
from apps.organizations.models import Organization, Stream

from .models import ConsentRecord, ParticipantToken


class EntryCodeInvalid(Exception):
    """Ссылка/QR не распознаны — ТЗ FR-01.4: токен при этом не создаётся."""


class StreamInvalid(Exception):
    """The selected stream is missing, inactive, or belongs to another organization."""


class BundleUnavailable(Exception):
    """The bundle is not assigned to this organization or participant."""


class SessionNotFound(Exception):
    """Токен не найден. Отдаём 404 без уточнений, чтобы не дать способ перебора токенов."""


class ConsentRequired(Exception):
    """Попытка сохранить ответ без действующего согласия на обработку ПД (ТЗ FR-03.3)."""


class NoActiveStage(Exception):
    """Оба этапа завершены, либо активные методики ещё не подключены методологом."""


class UnknownQuestion(Exception):
    """question_id/option_id не относятся к активному набору вопросов текущего этапа."""


class InvalidAnswerValue(Exception):
    """Для вопроса со свободным числовым вводом (например EQ-5D VAS) передан не 0–100."""


def active_questions(bundle: TestBundle | None = None) -> list[Question]:
    if bundle is None:
        bundle = TestBundle.objects.filter(is_active=True).order_by("id").first()
    if bundle is not None:
        versions = [
            item.questionnaire_version
            for item in bundle.items.select_related("questionnaire_version").all()
            if item.questionnaire_version.is_active
        ]
    else:
        versions = list(QuestionnaireVersion.objects.filter(is_active=True).order_by("code"))

    questions: list[Question] = []
    for version in versions:
        questions.extend(version.questions.prefetch_related("options").order_by("order"))
    return questions

def active_streams_for_entry_code(entry_code: str) -> list[Stream]:
    try:
        organization = Organization.objects.get(entry_code=entry_code)
    except Organization.DoesNotExist as exc:
        raise EntryCodeInvalid from exc
    return list(Stream.objects.filter(organization=organization, status=Stream.STATUS_ACTIVE).order_by("name", "code"))


def create_session(entry_code: str, stream_id: int | None = None) -> ParticipantToken:
    try:
        organization = Organization.objects.get(entry_code=entry_code)
    except Organization.DoesNotExist as exc:
        raise EntryCodeInvalid from exc

    # Если у клиента ровно один активный поток — привязываем участника к нему автоматически.
    # Несколько одновременных активных потоков или их отсутствие — участник остаётся без потока,
    # координатор сможет назначить его позже (открытый вопрос, см. README «Важные ограничения»).
    if stream_id is not None:
        stream = Stream.objects.filter(
            pk=stream_id, organization=organization, status=Stream.STATUS_ACTIVE
        ).first()
        if stream is None:
            raise StreamInvalid
    else:
        active_streams = Stream.objects.filter(organization=organization, status=Stream.STATUS_ACTIVE)
        stream = active_streams.first() if active_streams.count() == 1 else None

    # baseline_status и т.п. уже "not_started" по умолчанию на новой записи — отдельной
    # инициализации не нужно (раньше это была create() отдельной строки StageProgress).
    return ParticipantToken.objects.create(organization=organization, stream=stream)


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


def current_stage(token: ParticipantToken, bundle: TestBundle | None = None) -> Optional[str]:
    total = len(active_questions(bundle))
    if total == 0:
        return None

    answers = AnswerResponse.objects.filter(token=token)
    if bundle is not None:
        answers = answers.filter(bundle=bundle)
    baseline_answered = answers.filter(stage=ParticipantToken.STAGE_BASELINE).count()
    if baseline_answered < total:
        return ParticipantToken.STAGE_BASELINE
    followup_answered = answers.filter(stage=ParticipantToken.STAGE_FOLLOWUP).count()
    if followup_answered < total:
        return ParticipantToken.STAGE_FOLLOWUP
    return None


def get_bundle_for_token(token: ParticipantToken, bundle_id: int) -> TestBundle:
    bundle = TestBundle.objects.filter(pk=bundle_id).first()
    if bundle is None:
        raise BundleUnavailable
    assigned = token.organization.test_bundles.filter(pk=bundle.pk).exists()
    has_progress = AnswerResponse.objects.filter(token=token, bundle=bundle).exists()
    if not assigned and not has_progress:
        raise BundleUnavailable
    return bundle


def participant_home_state(token: ParticipantToken) -> dict:
    assigned_ids = set(token.organization.test_bundles.values_list("pk", flat=True))
    historical_ids = set(
        AnswerResponse.objects.filter(token=token, bundle__isnull=False).values_list("bundle_id", flat=True).distinct()
    )
    bundles = TestBundle.objects.filter(pk__in=assigned_ids | historical_ids).order_by("name", "code")
    bundle_payload = []

    for bundle in bundles:
        questions = active_questions(bundle)
        if not questions:
            continue
        answers = list(
            AnswerResponse.objects.filter(token=token, bundle=bundle).select_related("question")
        )
        answered = {
            ParticipantToken.STAGE_BASELINE: set(),
            ParticipantToken.STAGE_FOLLOWUP: set(),
        }
        answered_by_questionnaire = {
            ParticipantToken.STAGE_BASELINE: {},
            ParticipantToken.STAGE_FOLLOWUP: {},
        }
        for answer in answers:
            answered[answer.stage].add(answer.question_id)
            code = answer.question.questionnaire_version.code
            answered_by_questionnaire[answer.stage].setdefault(code, set()).add(answer.question_id)

        questionnaires = {}
        for question in questions:
            version = question.questionnaire_version
            item = questionnaires.setdefault(
                version.code,
                {
                    "code": version.code,
                    "name": version.get_code_display(),
                    "question_count": 0,
                    "baseline_answered": 0,
                    "followup_answered": 0,
                },
            )
            item["question_count"] += 1
        for code, item in questionnaires.items():
            item["baseline_answered"] = len(answered_by_questionnaire[ParticipantToken.STAGE_BASELINE].get(code, set()))
            item["followup_answered"] = len(answered_by_questionnaire[ParticipantToken.STAGE_FOLLOWUP].get(code, set()))

        total = len(questions)
        baseline_count = len(answered[ParticipantToken.STAGE_BASELINE])
        followup_count = len(answered[ParticipantToken.STAGE_FOLLOWUP])
        status = "completed" if followup_count >= total else "in_progress" if baseline_count or followup_count else "not_started"
        bundle_payload.append(
            {
                "id": bundle.pk,
                "code": bundle.code,
                "name": bundle.name,
                "status": status,
                "baseline": {"answered": baseline_count, "total": total},
                "followup": {"answered": followup_count, "total": total},
                "questionnaires": list(questionnaires.values()),
            }
        )

    return {"token": token.token, "consent_status": consent_status(token), "bundles": bundle_payload}

def _sync_stage_progress(token: ParticipantToken, bundle: TestBundle | None = None) -> None:
    total = len(active_questions(bundle))
    changed_fields = []
    for stage in (ParticipantToken.STAGE_BASELINE, ParticipantToken.STAGE_FOLLOWUP):
        answers = AnswerResponse.objects.filter(token=token, stage=stage)
        if bundle is not None:
            answers = answers.filter(bundle=bundle)
        answered = answers.count()
        if answered == 0:
            progress_status = ParticipantToken.PROGRESS_NOT_STARTED
        elif total and answered >= total:
            progress_status = ParticipantToken.PROGRESS_COMPLETED
        else:
            progress_status = ParticipantToken.PROGRESS_IN_PROGRESS

        status_field, started_field, completed_field = f"{stage}_status", f"{stage}_started_at", f"{stage}_completed_at"
        if getattr(token, status_field) != progress_status:
            setattr(token, status_field, progress_status)
            changed_fields.append(status_field)
            if progress_status == ParticipantToken.PROGRESS_IN_PROGRESS and not getattr(token, started_field):
                setattr(token, started_field, timezone.now())
                changed_fields.append(started_field)
            if progress_status == ParticipantToken.PROGRESS_COMPLETED and not getattr(token, completed_field):
                setattr(token, completed_field, timezone.now())
                changed_fields.append(completed_field)

    if changed_fields:
        token.save(update_fields=changed_fields)

def session_state(token: ParticipantToken, bundle: TestBundle | None = None) -> dict:
    consent = consent_status(token)
    stage = current_stage(token, bundle)
    questions = active_questions(bundle)
    show_questions = stage is not None and consent == "granted"

    answers_by_question = {}
    if show_questions:
        answers = AnswerResponse.objects.filter(token=token, stage=stage)
        if bundle is not None:
            answers = answers.filter(bundle=bundle)
        answers_by_question = {answer.question_id: answer for answer in answers}

    question_payload = []
    questionnaire_counts = {}
    if show_questions:
        for question in questions:
            version = question.questionnaire_version
            item = questionnaire_counts.setdefault(
                version.code,
                {"code": version.code, "name": version.get_code_display(), "question_count": 0, "answered_count": 0},
            )
            item["question_count"] += 1
            if question.id in answers_by_question:
                item["answered_count"] += 1
            answer = answers_by_question.get(question.id)
            question_payload.append(
                {
                    "id": question.id,
                    "code": question.code,
                    "text": question.text,
                    "indicator_code": question.indicator_code,
                    "questionnaire_code": version.code,
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

    stage_status = None
    if stage is not None:
        stage_answers = AnswerResponse.objects.filter(token=token, stage=stage)
        if bundle is not None:
            stage_answers = stage_answers.filter(bundle=bundle)
        answered_count = stage_answers.count()
        total_questions = len(questions)
        if answered_count == 0:
            stage_status = ParticipantToken.PROGRESS_NOT_STARTED
        elif answered_count >= total_questions:
            stage_status = ParticipantToken.PROGRESS_COMPLETED
        else:
            stage_status = ParticipantToken.PROGRESS_IN_PROGRESS

    return {
        "token": token.token,
        "bundle_id": bundle.pk if bundle else None,
        "bundle_name": bundle.name if bundle else "",
        "consent_status": consent,
        "stage": stage,
        "stage_status": stage_status,
        "questions": question_payload,
        "questionnaires": list(questionnaire_counts.values()),
        "progress": {
            "answered": sum(1 for item in question_payload if item["answer"] is not None),
            "total": len(questions),
        },
    }

def submit_answer(
    token: ParticipantToken, question_id: int, option_id: Optional[int], raw_value: str, bundle: TestBundle | None = None
) -> dict:
    if consent_status(token) != "granted":
        raise ConsentRequired

    stage = current_stage(token, bundle)
    if stage is None:
        raise NoActiveStage

    questions_by_id = {question.id: question for question in active_questions(bundle)}
    question = questions_by_id.get(question_id)
    if question is None:
        raise UnknownQuestion

    options = question.options.all()
    selected_option = None
    if options:
        if option_id is None:
            raise UnknownQuestion
        selected_option = next((option for option in options if option.id == option_id), None)
        if selected_option is None:
            raise UnknownQuestion
    else:
        if option_id is not None:
            raise UnknownQuestion
        try:
            numeric_value = int(raw_value)
        except (TypeError, ValueError):
            raise InvalidAnswerValue from None
        if not 0 <= numeric_value <= 100:
            raise InvalidAnswerValue

    AnswerResponse.objects.update_or_create(
        token=token,
        bundle=bundle,
        stage=stage,
        question=question,
        defaults={"selected_option": selected_option, "raw_value": raw_value},
    )
    _sync_stage_progress(token, bundle)
    _maybe_score_stage(token, stage, bundle)
    return session_state(token, bundle)

def _maybe_score_stage(token: ParticipantToken, stage: str, bundle: TestBundle | None = None) -> None:
    total = len(active_questions(bundle))
    answers = AnswerResponse.objects.filter(token=token, stage=stage)
    if bundle is not None:
        answers = answers.filter(bundle=bundle)
    if total and answers.count() >= total:
        compute_scores_for_stage(token, stage, bundle=bundle)
