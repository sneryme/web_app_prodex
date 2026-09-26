from django.contrib import admin

from .models import License, Organization, Stream


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "legal_name", "entry_code", "created_at"]
    search_fields = ["name", "legal_name", "entry_code"]


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ["organization", "starts_at", "ends_at", "status"]
    list_filter = ["status"]


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ["organization", "code", "status", "planned_start", "planned_end", "min_group_size"]
    list_filter = ["status"]
    search_fields = ["code", "name"]
