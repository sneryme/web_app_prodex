from rest_framework.permissions import BasePermission

from .models import StaffProfile


class IsStaffMember(BasePermission):
    """Доступ только сотрудникам с профилем StaffProfile (ТЗ FR-12-lite).

    Это не полноценный RBAC из ТЗ FR-12 (нет проверки конкретной роли на уровне пермишена,
    нет аудита) — только факт "это залогиненный сотрудник, а не аноним". Разграничение по
    ролям (кому какая организация видна) делает сам View, см. apps/reporting/views.py.
    """

    message = "Доступ только для авторизованных сотрудников."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "staff_profile"))


class IsProdexAdmin(BasePermission):
    """Доступ только администратору PRODEX (ТЗ FR-11.1).

    В отличие от employer-контура (`apps/reporting/views.py`), где чужая организация отдаёт 404,
    чтобы не раскрывать её существование, здесь скрывать нечего — сам контур PRODEX Admin не
    секрет, а администратору организации достаточно знать, что раздел ему не положен (403).
    DRF сам превращает это в 401, если пользователь вообще не аутентифицирован
    (см. `APIView.permission_denied`), поэтому отдельно проверять анонима не нужно.
    """

    message = "Доступ только для администратора PRODEX."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and hasattr(request.user, "staff_profile")):
            return False
        return request.user.staff_profile.role == StaffProfile.ROLE_PRODEX_ADMIN
