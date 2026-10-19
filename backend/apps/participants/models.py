import secrets

from django.db import models


def generate_token():
    """Случайный секретный токен участника вместо ФИО/телефона/e-mail (ТЗ п.3)."""
    return secrets.token_urlsafe(24)


class ParticipantToken(models.Model):
    """Анонимный профиль участника. Токен связывает вход и итог; работодатель этой связи не получает.

    Прогресс по этапам и персональный отчёт раньше жили в отдельных таблицах (`StageProgress`,
    `reporting.PersonalReportSnapshot`). У обеих всегда была ровно одна актуальная запись на
    токен — это не журнал и не растущая со временем коллекция, а просто текущее состояние, поэтому
    они свёрнуты в поля прямо здесь. Если когда-нибудь понадобится хранить ИСТОРИЮ пересчётов
    отчёта (а не только последний), это будет веский повод завести отдельную таблицу обратно.
    """

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Активен"),
        (STATUS_COMPLETED, "Завершён"),
        (STATUS_REVOKED, "Отозван"),
    ]

    STAGE_BASELINE = "baseline"
    STAGE_FOLLOWUP = "followup"

    PROGRESS_NOT_STARTED = "not_started"
    PROGRESS_IN_PROGRESS = "in_progress"
    PROGRESS_COMPLETED = "completed"
    PROGRESS_STATUS_CHOICES = [
        (PROGRESS_NOT_STARTED, "Не начат"),
        (PROGRESS_IN_PROGRESS, "В процессе"),
        (PROGRESS_COMPLETED, "Завершён"),
    ]

    token = models.CharField(max_length=64, unique=True, db_index=True, default=generate_token)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="participant_tokens"
    )
    stream = models.ForeignKey(
        "organizations.Stream", on_delete=models.SET_NULL, null=True, blank=True, related_name="participant_tokens"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    # Прогресс по этапам (бывшая таблица StageProgress) — производный кэш для будущей аналитики
    # completion (ТЗ FR-09), не источник истины: текущий этап всегда пересчитывается заново из
    # AnswerResponse в apps/participants/services.py::current_stage().
    baseline_status = models.CharField(max_length=16, choices=PROGRESS_STATUS_CHOICES, default=PROGRESS_NOT_STARTED)
    baseline_started_at = models.DateTimeField(null=True, blank=True)
    baseline_completed_at = models.DateTimeField(null=True, blank=True)
    followup_status = models.CharField(max_length=16, choices=PROGRESS_STATUS_CHOICES, default=PROGRESS_NOT_STARTED)
    followup_started_at = models.DateTimeField(null=True, blank=True)
    followup_completed_at = models.DateTimeField(null=True, blank=True)

    # Персональный отчёт (бывшая таблица reporting.PersonalReportSnapshot) — кэш последнего
    # собранного отчёта; источник истины — ScoringResult, отчёт пересобирается им заново при
    # каждом обращении к build_personal_report() (ТЗ FR-08).
    report_payload = models.JSONField(null=True, blank=True)
    report_generated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.token


class ConsentRecord(models.Model):
    """Журнал согласий: версия текста и факт согласия — отдельно от прочих подтверждений (ТЗ FR-03.4, п.6)."""

    TYPE_DATA_PROCESSING = "data_processing"
    TYPE_INFORMED_NOTICE = "informed_notice"
    TYPE_CHOICES = [
        (TYPE_DATA_PROCESSING, "Согласие на обработку персональных данных"),
        (TYPE_INFORMED_NOTICE, "Информирование участника"),
    ]

    token = models.ForeignKey(ParticipantToken, on_delete=models.CASCADE, related_name="consents")
    consent_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    text_version = models.CharField(max_length=32)
    accepted = models.BooleanField()
    accepted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.token_id}:{self.consent_type}:{self.text_version}"
