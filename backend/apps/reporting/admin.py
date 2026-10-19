from django.contrib import admin

from .models import AggregateSnapshot, ExportArtifact

# Персональный отчёт участника теперь смотрят в ParticipantTokenAdmin (apps/participants/admin.py) —
# поля report_payload/report_generated_at, бывшая отдельная модель PersonalReportSnapshot.


@admin.register(AggregateSnapshot)
class AggregateSnapshotAdmin(admin.ModelAdmin):
    list_display = ["organization", "stream", "stage", "indicator_code", "participant_count", "is_suppressed", "generated_at"]
    list_filter = ["stage", "is_suppressed", "organization"]


@admin.register(ExportArtifact)
class ExportArtifactAdmin(admin.ModelAdmin):
    list_display = ["organization", "stream", "kind", "requested_by", "generated_at"]
    list_filter = ["kind", "organization"]
