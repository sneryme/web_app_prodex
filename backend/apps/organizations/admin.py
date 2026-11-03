from django.contrib import admin

from .models import License, Organization, Stream


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "legal_name", "entry_code", "created_at"]
    search_fields = ["name", "legal_name", "entry_code"]
    filter_horizontal = ["test_bundles"]


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ["organization", "starts_at", "ends_at", "status"]
    list_filter = ["status"]


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ["organization", "name", "code", "status", "planned_start", "planned_end", "min_group_size"]
    list_filter = ["organization", "status"]
    search_fields = ["organization__name", "code", "name"]
