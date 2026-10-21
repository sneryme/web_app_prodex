from rest_framework.permissions import BasePermission


class IsStaffMember(BasePermission):
    """Доступ только сотрудникам с профилем StaffProfile (ТЗ FR-12-lite).

    Это не полноценный RBAC из ТЗ FR-12 (нет проверки конкретной роли на уровне пермишена,
    нет аудита) — только факт "это залогиненный сотрудник, а не аноним". Разграничение по
    ролям (кому какая организация видна) делает сам View, см. apps/reporting/views.py.
    """

    message = "Доступ только для авторизованных сотрудников."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "staff_profile"))
