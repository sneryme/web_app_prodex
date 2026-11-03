from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.reporting.services import ReportNotReady, build_personal_report

from . import services
from .serializers import (
    AnswerSerializer,
    ConsentSerializer,
    CreateSessionSerializer,
    ListStreamsSerializer,
    SelectBundleSerializer,
)


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
        token = services.create_session(
            serializer.validated_data["entry_code"], serializer.validated_data.get("stream_id")
        )
    except services.EntryCodeInvalid:
        return Response(
            {"detail": "Ссылка недействительна или отключена."}, status=status.HTTP_404_NOT_FOUND
        )
    except services.StreamInvalid:
        return Response({"detail": "Selected stream is unavailable."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(services.participant_home_state(token), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def list_entry_streams(request):
    serializer = ListStreamsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        streams = services.active_streams_for_entry_code(serializer.validated_data["entry_code"])
    except services.EntryCodeInvalid:
        return Response({"detail": "Ссылка недействительна."}, status=status.HTTP_404_NOT_FOUND)
    return Response([{"id": stream.id, "code": stream.code, "name": stream.name or stream.code} for stream in streams])


@api_view(["GET"])
def session_detail(request, token):
    """FR-01.3/FR-04: состояние сессии — по нему фронтенд решает, какой экран показать."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    return Response(services.participant_home_state(participant_token))


@api_view(["POST"])
def session_bundle(request, token):
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    serializer = SelectBundleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        bundle = services.get_bundle_for_token(participant_token, serializer.validated_data["bundle_id"])
    except services.BundleUnavailable:
        return Response({"detail": "Selected test bundle is unavailable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(services.session_state(participant_token, bundle))


@api_view(["POST"])
def session_consent(request, token):
    """FR-03.4: факт согласия и версия текста фиксируются в журнале."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    serializer = ConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data.copy()
    bundle_id = data.pop("bundle_id", None)
    services.record_consent(participant_token, **data)
    if bundle_id is None:
        return Response(services.session_state(participant_token), status=status.HTTP_201_CREATED)
    try:
        bundle = services.get_bundle_for_token(participant_token, bundle_id)
    except services.BundleUnavailable:
        return Response({"detail": "Selected test bundle is unavailable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(services.session_state(participant_token, bundle), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def session_answer(request, token):
    """FR-06.6: сохранение ответа — идемпотентно; без согласия или вне активного этапа — отказ."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    serializer = AnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        bundle_id = serializer.validated_data.get("bundle_id")
        bundle = services.get_bundle_for_token(participant_token, bundle_id) if bundle_id is not None else None
        state = services.submit_answer(
            participant_token,
            question_id=serializer.validated_data["question_id"],
            option_id=serializer.validated_data["option_id"],
            raw_value=serializer.validated_data["raw_value"],
            bundle=bundle,
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
    except services.InvalidAnswerValue:
        return Response(
            {"detail": "Ответ должен быть числом от 0 до 100."}, status=status.HTTP_400_BAD_REQUEST
        )
    except services.BundleUnavailable:
        return Response({"detail": "Selected test bundle is unavailable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(state)


@api_view(["GET"])
def session_report(request, token):
    """FR-08: персональный отчёт «до/после». FR-08.7: неверный токен и «отчёт ещё не готов» — оба 404."""
    participant_token, error = _get_token_or_404(token)
    if error is not None:
        return error
    bundle_id = request.query_params.get("bundle_id")
    try:
        bundle = services.get_bundle_for_token(participant_token, int(bundle_id)) if bundle_id else None
    except (services.BundleUnavailable, ValueError):
        return Response({"detail": "Test bundle not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        report = build_personal_report(participant_token, bundle=bundle)
    except ReportNotReady:
        return Response(
            {"detail": "Отчёт появится после завершения обоих этапов тестирования."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(report)
