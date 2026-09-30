from django.contrib import admin

from .models import AuditEvent, StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "organization", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email"]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type"]
    readonly_fields = ["actor", "action", "target_type", "target_id", "metadata", "created_at"]
