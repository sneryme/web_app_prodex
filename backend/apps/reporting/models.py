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
        "organizations.Organization", on_delete=models.CASCADE, related_name="aggregate_snapshots", verbose_name="Организация"
    )
    stream = models.ForeignKey(
        "organizations.Stream",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="aggregate_snapshots",
        verbose_name="Поток",
    )
    stage = models.CharField("Этап", max_length=16, choices=STAGE_CHOICES)
    indicator_code = models.CharField("Код показателя", max_length=32)
    participant_count = models.PositiveIntegerField("Количество участников")
    metrics = models.JSONField("Метрики", help_text="Среднее/медиана/распределение по показателю.")
    is_suppressed = models.BooleanField(
        "Скрыт (маленькая группа)",
        default=False,
        help_text="True, если participant_count меньше min_group_size потока (ТЗ FR-09.4).",
    )
    generated_at = models.DateTimeField("Сформирован", auto_now_add=True)

    class Meta:
        verbose_name = "Групповой агрегат"
        verbose_name_plural = "Групповые агрегаты"

    def __str__(self):
        return f"aggregate:{self.organization_id}:{self.indicator_code}:{self.stage}"


class ExportArtifact(models.Model):
    """Сформированный PDF/XLSX/CSV-экспорт; строки участников и токены в файл не попадают (ТЗ FR-10.1/10.2)."""

    KIND_PDF = "pdf"
    KIND_XLSX = "xlsx"
    KIND_CSV = "csv"
    KIND_CHOICES = [(KIND_PDF, "PDF"), (KIND_XLSX, "XLSX"), (KIND_CSV, "CSV")]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="export_artifacts", verbose_name="Организация"
    )
    stream = models.ForeignKey(
        "organizations.Stream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_artifacts",
        verbose_name="Поток",
    )
    kind = models.CharField("Тип", max_length=8, choices=KIND_CHOICES)
    requested_by = models.ForeignKey(
        "identity.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_artifacts",
        verbose_name="Запросил",
    )
    file = models.FileField("Файл", upload_to="exports/%Y/%m/")
    generated_at = models.DateTimeField("Сформирован", auto_now_add=True)

    class Meta:
        verbose_name = "Экспорт"
        verbose_name_plural = "Экспорты"

    def __str__(self):
        return f"{self.kind}:{self.organization_id}:{self.generated_at:%Y-%m-%d}"
