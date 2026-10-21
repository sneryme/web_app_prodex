from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import services
from .permissions import IsStaffMember


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """Вход сотрудника (ТЗ FR-12-lite — временная замена полному RBAC из ТЗ FR-12).

    Логин/пароль стандартного django.contrib.auth.User; доступ только тем, у кого есть
    identity.StaffProfile — участник теста сюда попасть не может (у него нет User вовсе).
    """
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        # Сотрудник не установлен, поэтому actor=None; логин нужен, чтобы запись была полезной,
        # пароль в журнал не попадает (см. apps/identity/services.py).
        services.record_event(
            action=services.ACTION_LOGIN_FAILED, metadata={"username": username, "reason": "bad_credentials"}
        )
        return Response({"detail": "Неверный логин или пароль."}, status=status.HTTP_401_UNAUTHORIZED)

    profile = getattr(user, "staff_profile", None)
    if profile is None:
        services.record_event(
            action=services.ACTION_LOGIN_FAILED, metadata={"username": username, "reason": "no_staff_profile"}
        )
        return Response({"detail": "У пользователя нет профиля сотрудника."}, status=status.HTTP_403_FORBIDDEN)

    token, _ = Token.objects.get_or_create(user=user)
    services.record_event(action=services.ACTION_LOGIN, actor=profile)
    return Response(
        {
            "token": token.key,
            "role": profile.role,
            "role_display": profile.get_role_display(),
            "organization": (
                {"id": profile.organization_id, "name": profile.organization.name}
                if profile.organization_id
                else None
            ),
        }
    )


@api_view(["POST"])
@permission_classes([IsStaffMember])
def logout(request):
    services.record_event(action=services.ACTION_LOGOUT, actor=request.user.staff_profile)
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
