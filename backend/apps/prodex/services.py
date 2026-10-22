"""Операционные данные для администратора PRODEX (ТЗ FR-11).

Намеренно без психологических показателей участников (ТЗ FR-11.5) — это главное отличие от
`apps.reporting.employer_services`, который считает групповые психологические агрегаты для
работодателя. Здесь — только организационные и технические данные: клиенты, лицензии, потоки,
completion, активность, ошибки подсчёта.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from apps.assessments.models import AnswerResponse, ScoringResult
from apps.organizations.models import License, Organization, Stream
from apps.participants.models import ParticipantToken


def _license_payload(license_obj: License | None) -> dict | None:
    if license_obj is None:
        return None
    return {
        "id": license_obj.id,
        "starts_at": license_obj.starts_at,
        "ends_at": license_obj.ends_at,
        "status": license_obj.status,
        "status_display": license_obj.get_status_display(),
        # Статус истечения считаем от даты, а не только от хранимого `status` (ТЗ FR-11.3):
        # `status` сотрудник выставляет руками (например "suspended"), а срок истекает сам по
        # себе — админке нужно видеть оба факта отдельно, не подменяя один другим.
        "is_expired": license_obj.ends_at < timezone.localdate(),
    }


def _current_license(organization) -> License | None:
    """Актуальная (последняя по сроку действия) лицензия юрлица. Лицензия выдаётся одна на
    юрлицо за раз (ТЗ FR-11.3), но со временем перевыпускается, поэтому строк может быть
    несколько — берём последнюю по `ends_at`."""
    return organization.licenses.order_by("-ends_at").first()


def list_clients(*, license_status: str | None = None, search: str = "") -> list[dict]:
    """ТЗ FR-11.2: таблица клиентов со статусами лицензии и фильтрами."""
    organizations = Organization.objects.all().order_by("name")
    if search:
        organizations = organizations.filter(name__icontains=search)

    result = []
    for organization in organizations:
        license_obj = _current_license(organization)
        if license_status and (license_obj is None or license_obj.status != license_status):
            continue
        result.append(
            {
                "id": organization.id,
                "name": organization.name,
                "legal_name": organization.legal_name,
                "license": _license_payload(license_obj),
                "streams_count": organization.streams.count(),
                "participants_count": organization.participant_tokens.count(),
            }
        )
    return result


def list_licenses(*, status: str | None = None) -> list[dict]:
    """ТЗ FR-11.3: все лицензии (включая историю перевыпуска), не только актуальная на клиента."""
    licenses = License.objects.select_related("organization").order_by("-ends_at")
    if status:
        licenses = licenses.filter(status=status)
    return [
        {**_license_payload(lic), "organization": {"id": lic.organization_id, "name": lic.organization.name}}
        for lic in licenses
    ]


def _unscored_answer_groups_count() -> int:
    """Технический индикатор ошибок (ТЗ FR-11.4): сколько пар «участник/этап/показатель» имеют
    ответы, но не имеют `ScoringResult`. В норме таких нет — расчёт идёт синхронно при каждом
    ответе (`apps/assessments/scoring.py::compute_scores_for_stage`). Ненулевое значение почти
    всегда означает пропуск из-за смешанной версии методики (ответы одного показателя из двух
    версий опросника — тот же случай, что пишет `logger.warning` в scoring.py); здесь это просто
    агрегируется в одно число для операционного мониторинга, без указания, какому конкретно
    участнику или ответу оно принадлежит (ТЗ FR-11.5 — психологических данных здесь нет)."""
    answered = set(AnswerResponse.objects.values_list("token_id", "stage", "question__indicator_code"))
    scored = set(ScoringResult.objects.values_list("token_id", "stage", "indicator_code"))
    return len(answered - scored)


def operations_overview() -> dict:
    """ТЗ FR-11.4: потоки, completion, активность, ошибки и технические метрики по всей системе
    (администратор PRODEX видит всё, в отличие от работодателя — Положение о ролях, п. 2)."""
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    return {
        "organizations_count": Organization.objects.count(),
        "licenses": {choice: License.objects.filter(status=choice).count() for choice, _ in License.STATUS_CHOICES},
        "streams": {choice: Stream.objects.filter(status=choice).count() for choice, _ in Stream.STATUS_CHOICES},
        "participants": {
            "total": ParticipantToken.objects.count(),
            **{
                choice: ParticipantToken.objects.filter(status=choice).count()
                for choice, _ in ParticipantToken.STATUS_CHOICES
            },
        },
        "completion": {
            "baseline_completed": ParticipantToken.objects.filter(
                baseline_status=ParticipantToken.PROGRESS_COMPLETED
            ).count(),
            "followup_completed": ParticipantToken.objects.filter(
                followup_status=ParticipantToken.PROGRESS_COMPLETED
            ).count(),
        },
        "activity": {
            "new_participants_last_30d": ParticipantToken.objects.filter(created_at__gte=thirty_days_ago).count(),
        },
        "errors": {"unscored_answer_groups": _unscored_answer_groups_count()},
    }
