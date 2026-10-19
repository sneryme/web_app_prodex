from django.db import models

# Персональный отчёт участника (бывшая таблица PersonalReportSnapshot) теперь — поля
# report_payload/report_generated_at на apps.participants.ParticipantToken: у токена всегда
# максимум одна актуальная запись, это не журнал. См. комментарий в participants/models.py.


class AggregateSnapshot(models.Model):
    """Обезличенный групповой агрегат для employer dashboard и экспортов (ТЗ FR-09/FR-10)."""

    STAGE_CHOICES = [
        ("baseline", "Входное тестирование"),
        ("followup", "Итоговое тестирование"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="aggregate_snapshots"
    )
    stream = models.ForeignKey(
        "organizations.Stream", on_delete=models.CASCADE, null=True, blank=True, related_name="aggregate_snapshots"
    )
    stage = models.CharField(max_length=16, choices=STAGE_CHOICES)
    indicator_code = models.CharField(max_length=32)
    participant_count = models.PositiveIntegerField()
    metrics = models.JSONField(help_text="Среднее/медиана/распределение по показателю.")
    is_suppressed = models.BooleanField(
        default=False, help_text="True, если participant_count меньше min_group_size потока (ТЗ FR-09.4)."
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"aggregate:{self.organization_id}:{self.indicator_code}:{self.stage}"


class ExportArtifact(models.Model):
    """Сформированный PDF/XLSX-экспорт; строки участников и токены в файл не попадают (ТЗ FR-10.1/10.2)."""

    KIND_PDF = "pdf"
    KIND_XLSX = "xlsx"
    KIND_CHOICES = [(KIND_PDF, "PDF"), (KIND_XLSX, "XLSX")]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="export_artifacts"
    )
    stream = models.ForeignKey(
        "organizations.Stream", on_delete=models.SET_NULL, null=True, blank=True, related_name="export_artifacts"
    )
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    requested_by = models.ForeignKey(
        "identity.StaffProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="export_artifacts"
    )
    file = models.FileField(upload_to="exports/%Y/%m/")
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind}:{self.organization_id}:{self.generated_at:%Y-%m-%d}"
