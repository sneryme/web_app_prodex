from django.conf import settings
from django.db import models


class StaffProfile(models.Model):
    """Роль сотрудника для RBAC (ТЗ FR-12): участник в эту модель не входит — у него нет логина."""

    ROLE_COORDINATOR = "coordinator"
    ROLE_HR = "hr"
    ROLE_PRODEX_ACCOUNT = "prodex_account"
    ROLE_METHODOLOGIST = "methodologist"
    ROLE_SYSADMIN = "sysadmin"
    ROLE_CHOICES = [
        (ROLE_COORDINATOR, "Координатор"),
        (ROLE_HR, "HR"),
        (ROLE_PRODEX_ACCOUNT, "PRODEX account"),
        (ROLE_METHODOLOGIST, "Методолог"),
        (ROLE_SYSADMIN, "Системный администратор"),
    ]
    # Координатор и HR привязаны к организации-клиенту; остальные роли — нет.
    ORG_SCOPED_ROLES = {ROLE_COORDINATOR, ROLE_HR}

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="staff_members",
        null=True,
        blank=True,
        help_text="Обязательно для координатора/HR; пусто для PRODEX account, методолога и сисадмина.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"


class AuditEvent(models.Model):
    """Журнал критичных действий сотрудников (ТЗ FR-12.6)."""

    actor = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events"
    )
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
