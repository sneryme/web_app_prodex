from django.contrib import admin

from .models import AuditEvent, StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "organization", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email"]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Журнал только на чтение: записи создаёт код (`identity/services.py`), не человек.

    `readonly_fields` сам по себе запрещает лишь правку полей — через админку всё ещё можно было
    бы добавить запись задним числом или удалить неудобную. Журнал, в котором можно дописать или
    стереть строку, не выполняет своей задачи (Положение о ролях, п. 5.3), поэтому добавление и
    удаление закрыты тоже. Правка не закрыта отдельным методом: все поля уже readonly.
    """

    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type"]
    readonly_fields = ["actor", "action", "target_type", "target_id", "metadata", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
