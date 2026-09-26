from django.contrib import admin

from .models import AggregateSnapshot, ExportArtifact, PersonalReportSnapshot


@admin.register(PersonalReportSnapshot)
class PersonalReportSnapshotAdmin(admin.ModelAdmin):
    # Только для инженерной отладки: содержит персональный результат участника.
    list_display = ["token", "generated_at"]


@admin.register(AggregateSnapshot)
class AggregateSnapshotAdmin(admin.ModelAdmin):
    list_display = ["organization", "stream", "stage", "indicator_code", "participant_count", "is_suppressed", "generated_at"]
    list_filter = ["stage", "is_suppressed", "organization"]


@admin.register(ExportArtifact)
class ExportArtifactAdmin(admin.ModelAdmin):
    list_display = ["organization", "stream", "kind", "requested_by", "generated_at"]
    list_filter = ["kind", "organization"]
