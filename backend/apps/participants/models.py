import secrets

from django.db import models


def generate_token():
    """Случайный секретный токен участника вместо ФИО/телефона/e-mail (ТЗ п.3)."""
    return secrets.token_urlsafe(24)


class ParticipantToken(models.Model):
    """Анонимный профиль участника. Токен связывает вход и итог; работодатель этой связи не получает."""

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Активен"),
        (STATUS_COMPLETED, "Завершён"),
        (STATUS_REVOKED, "Отозван"),
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


class StageProgress(models.Model):
    """Прогресс участника по этапу; система сама определяет вход/итог, ручного выбора нет (ТЗ FR-04)."""

    STAGE_BASELINE = "baseline"
    STAGE_FOLLOWUP = "followup"
    STAGE_CHOICES = [
        (STAGE_BASELINE, "Входное тестирование"),
        (STAGE_FOLLOWUP, "Итоговое тестирование"),
    ]

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Не начат"),
        (STATUS_IN_PROGRESS, "В процессе"),
        (STATUS_COMPLETED, "Завершён"),
    ]

    token = models.ForeignKey(ParticipantToken, on_delete=models.CASCADE, related_name="stage_progress")
    stage = models.CharField(max_length=16, choices=STAGE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("token", "stage")]

    def __str__(self):
        return f"{self.token_id}:{self.stage}:{self.status}"
