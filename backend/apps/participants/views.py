from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.reporting.services import ReportNotReady, build_personal_report

from . import services
from .serializers import AnswerSerializer, ConsentSerializer, CreateSessionSerializer


def _get_token_or_404(token_value):
    try:
        return services.get_token(token_value), None
    except services.SessionNotFound:
        return None, Response({"detail": "Сессия не найдена."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
def create_session(request):
    """FR-01.1/FR-01.4: корпоративная ссылка создаёт токен; неверный код — понятная ошибка без токена."""
    serializer = CreateSessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        token = services.create_session(serializer.validated_data["entry_code"])
    except services.EntryCodeInvalid:
        return Response(
            {"detail": "Ссылка недействительна или отключена."}, status=status.HTTP_404_NOT_FOUND
        )
    return Response(services.session_state(token), status=status.HTTP_201_CREATED)


@api_view(["GET"])
def session_detail(request, token):
    """FR-01.3/FR-04: состояние сессии — по нему фронтенд решает, какой экран показать."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    return Response(services.session_state(participant_token))


@api_view(["POST"])
def session_consent(request, token):
    """FR-03.4: факт согласия и версия текста фиксируются в журнале."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    serializer = ConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.record_consent(participant_token, **serializer.validated_data)
    return Response(services.session_state(participant_token), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def session_answer(request, token):
    """FR-06.6: сохранение ответа — идемпотентно; без согласия или вне активного этапа — отказ."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    serializer = AnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        state = services.submit_answer(
            participant_token,
            question_id=serializer.validated_data["question_id"],
            option_id=serializer.validated_data["option_id"],
            raw_value=serializer.validated_data["raw_value"],
        )
    except services.ConsentRequired:
        return Response(
            {"detail": "Нужно согласие на обработку персональных данных."}, status=status.HTTP_403_FORBIDDEN
        )
    except services.NoActiveStage:
        return Response(
            {"detail": "Активный этап тестирования не найден."}, status=status.HTTP_409_CONFLICT
        )
    except services.UnknownQuestion:
        return Response(
            {"detail": "Вопрос не относится к текущему этапу."}, status=status.HTTP_400_BAD_REQUEST
        )
    return Response(state)


@api_view(["GET"])
def session_report(request, token):
    """FR-08: персональный отчёт «до/после». FR-08.7: неверный токен и «отчёт ещё не готов» — оба 404."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    try:
        report = build_personal_report(participant_token)
    except ReportNotReady:
        return Response(
            {"detail": "Отчёт появится после завершения обоих этапов тестирования."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(report)
