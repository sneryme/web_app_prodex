from django.contrib import admin

from .models import ConsentRecord, ParticipantToken


class ConsentRecordInline(admin.TabularInline):
    model = ConsentRecord
    extra = 0
    readonly_fields = ["consent_type", "text_version", "accepted", "accepted_at"]
    can_delete = False


@admin.register(ParticipantToken)
class ParticipantTokenAdmin(admin.ModelAdmin):
    # Токен виден только внутри админки для инженерной поддержки: работодатель и PRODEX по умолчанию
    # доступа к этому экрану не имеют — доступ разграничивается на уровне RBAC (ТЗ п.3, FR-12).
    list_display = ["token", "organization", "stream", "status", "baseline_status", "followup_status", "created_at"]
    list_filter = ["status", "baseline_status", "followup_status", "organization", "stream"]
    search_fields = ["token"]
    readonly_fields = ["report_payload", "report_generated_at"]
    inlines = [ConsentRecordInline]
