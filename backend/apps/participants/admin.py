from django.contrib import admin

from .models import ConsentRecord, ParticipantToken, StageProgress


class ConsentRecordInline(admin.TabularInline):
    model = ConsentRecord
    extra = 0
    readonly_fields = ["consent_type", "text_version", "accepted", "accepted_at"]
    can_delete = False


class StageProgressInline(admin.TabularInline):
    model = StageProgress
    extra = 0


@admin.register(ParticipantToken)
class ParticipantTokenAdmin(admin.ModelAdmin):
    # Токен виден только внутри админки для инженерной поддержки: работодатель и PRODEX по умолчанию
    # доступа к этому экрану не имеют — доступ разграничивается на уровне RBAC (ТЗ п.3, FR-12).
    list_display = ["token", "organization", "stream", "status", "created_at"]
    list_filter = ["status", "organization", "stream"]
    search_fields = ["token"]
    inlines = [ConsentRecordInline, StageProgressInline]
