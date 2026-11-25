from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .models import License, Organization, Stream


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "legal_name", "entry_code", "copy_entry_link", "created_at"]
    search_fields = ["name", "legal_name", "entry_code"]
    list_filter = ["is_demo"]
    filter_horizontal = ["test_bundles"]

    class Media:
        js = ("organizations/admin.js",)

    @admin.display(description="Ссылка для участников")
    def copy_entry_link(self, obj):
        url = f"{settings.PARTICIPANT_FRONTEND_URL.rstrip('/')}?{urlencode({'code': obj.entry_code})}"
        return format_html(
            '<button type="button" class="button js-copy-entry-link" data-copy-url="{}">Скопировать ссылку</button>',
            url,
        )


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ["organization", "starts_at", "ends_at", "status"]
    list_filter = ["status"]


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ["organization", "display_name", "status", "planned_start", "planned_end"]
    list_filter = ["organization", "status"]
    search_fields = ["organization__name", "code", "name"]
    exclude = ["code", "min_group_size"]

    @admin.display(description="Название потока", ordering="name")
    def display_name(self, obj):
        return obj.name or f"Поток {obj.pk}"
