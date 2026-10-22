from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.identity.permissions import IsProdexAdmin

from . import services


@api_view(["GET"])
@permission_classes([IsProdexAdmin])
def list_clients(request):
    """ТЗ FR-11.2: таблица клиентов со статусом лицензии; ?search= и ?license_status= — фильтры."""
    return Response(
        services.list_clients(
            license_status=request.query_params.get("license_status") or None,
            search=request.query_params.get("search", ""),
        )
    )


@api_view(["GET"])
@permission_classes([IsProdexAdmin])
def list_licenses(request):
    """ТЗ FR-11.3: лицензия — одно юрлицо, срок, статус истечения; ?status= — фильтр."""
    return Response(services.list_licenses(status=request.query_params.get("status") or None))


@api_view(["GET"])
@permission_classes([IsProdexAdmin])
def operations(request):
    """ТЗ FR-11.4/FR-11.5: потоки, completion, активность, ошибки — без психологических данных."""
    return Response(services.operations_overview())
