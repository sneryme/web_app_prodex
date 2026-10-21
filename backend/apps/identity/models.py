from django.conf import settings
from django.db import models


class StaffProfile(models.Model):
    """Роль сотрудника для RBAC (ТЗ FR-12).

    «Положение о пользовательских ролях» задаёт три роли: участник, администратор организации и
    администратор PRODEX. Участник в эту модель не входит — у него нет логина вовсе, его «роль»
    выражена самим `participants.ParticipantToken`. Поэтому здесь ровно две роли сотрудников.

    Раньше их было пять (координатор, HR, PRODEX account, методолог, сисадмин) — Положение
    объединило первые две в администратора организации, а последние три в администратора PRODEX.
    Если внутри PRODEX снова понадобится градация (например, отдельный доступ методолога к
    редактору методик), это стоит делать отдельными разрешениями, а не новыми ролями: Положение,
    п. 5.3, требует разграничения именно по доступу к данным, а не по названию должности.
    """

    ROLE_ORG_ADMIN = "org_admin"
    ROLE_PRODEX_ADMIN = "prodex_admin"
    ROLE_CHOICES = [
        (ROLE_ORG_ADMIN, "Администратор организации"),
        (ROLE_PRODEX_ADMIN, "Администратор PRODEX"),
    ]
    # Администратор организации привязан к своему юрлицу; администратор PRODEX — нет.
    ORG_SCOPED_ROLES = {ROLE_ORG_ADMIN}

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile", verbose_name="Пользователь"
    )
    role = models.CharField("Роль", max_length=32, choices=ROLE_CHOICES)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="staff_members",
        null=True,
        blank=True,
        verbose_name="Организация",
        help_text="Обязательно для координатора/HR; пусто для PRODEX account, методолога и сисадмина.",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль сотрудника"
        verbose_name_plural = "Профили сотрудников"

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"


class AuditEvent(models.Model):
    """Журнал критичных действий сотрудников (ТЗ FR-12.6)."""

    actor = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events", verbose_name="Исполнитель"
    )
    action = models.CharField("Действие", max_length=128)
    target_type = models.CharField("Тип объекта", max_length=64, blank=True)
    target_id = models.CharField("ID объекта", max_length=64, blank=True)
    metadata = models.JSONField("Метаданные", default=dict, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Событие аудита"
        verbose_name_plural = "Журнал аудита"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
