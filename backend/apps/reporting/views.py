from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.assessments.models import TestBundle
from apps.identity import services as identity_services
from apps.identity.models import StaffProfile
from apps.identity.permissions import IsStaffMember
from apps.organizations.models import Organization, Stream

from . import employer_services, export_services


def _visible_organizations(staff_profile):
    """Администратор организации видит только своё юрлицо; администратор PRODEX — все
    (Положение о ролях, п. 2; см. StaffProfile.ORG_SCOPED_ROLES)."""
    if staff_profile.role in StaffProfile.ORG_SCOPED_ROLES:
        if staff_profile.organization_id is None:
            return Organization.objects.none()
        return Organization.objects.filter(pk=staff_profile.organization_id)
    return Organization.objects.all()


def _get_organization_or_404(request, organization_id):
    organizations = _visible_organizations(request.user.staff_profile)
    try:
        return organizations.get(pk=organization_id), None
    except (Organization.DoesNotExist, ValueError):
        # Намеренно 404, а не 403: координатору другой организации не нужно даже знать,
        # существует ли такой organization_id.
        return None, Response({"detail": "Организация не найдена."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsStaffMember])
def list_organizations(request):
    organizations = _visible_organizations(request.user.staff_profile).order_by("name")
    return Response([{"id": org.id, "name": org.name} for org in organizations])


@api_view(["GET"])
@permission_classes([IsStaffMember])
def organization_streams(request, organization_id):
    """ТЗ FR-09.3: список потоков организации — для фильтра на дашборде."""
    organization, error = _get_organization_or_404(request, organization_id)
    if error is not None:
        return error
    return Response(employer_services.list_streams(organization))


@api_view(["GET"])
@permission_classes([IsStaffMember])
def organization_bundles(request, organization_id):
    organization, error = _get_organization_or_404(request, organization_id)
    if error is not None:
        return error
    return Response(employer_services.list_bundles(organization))


def _resolve_stream(organization, request):
    stream_id = request.query_params.get("stream")
    if not stream_id:
        return None, None
    try:
        return Stream.objects.get(pk=stream_id, organization=organization), None
    except (Stream.DoesNotExist, ValueError):
        return None, Response({"detail": "Поток не найден в этой организации."}, status=status.HTTP_404_NOT_FOUND)


def _resolve_bundle(organization, request):
    bundle_id = request.query_params.get("bundle")
    if not bundle_id:
        return organization.test_bundles.order_by("name", "id").first(), None
    try:
        return organization.test_bundles.get(pk=bundle_id), None
    except (TestBundle.DoesNotExist, ValueError):
        return None, Response({"detail": "Комплект не найден в этой организации."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsStaffMember])
def organization_overview(request, organization_id):
    """ТЗ FR-09.2/FR-09.4/FR-09.5: охват, completion, 5 показателей «вход/итог», малые группы скрыты."""
    organization, error = _get_organization_or_404(request, organization_id)
    if error is not None:
        return error

    stream, error = _resolve_stream(organization, request)
    if error is not None:
        return error

    bundle, error = _resolve_bundle(organization, request)
    if error is not None:
        return error

    return Response(employer_services.organization_overview(organization, stream=stream, bundle=bundle))


@api_view(["GET"])
@permission_classes([IsStaffMember])
def organization_export(request, organization_id):
    """ТЗ FR-10: PDF/XLSX-экспорт того же агрегата, что и дашборд (?format=pdf|xlsx)."""
    organization, error = _get_organization_or_404(request, organization_id)
    if error is not None:
        return error

    stream, error = _resolve_stream(organization, request)
    if error is not None:
        return error

    bundle, error = _resolve_bundle(organization, request)
    if error is not None:
        return error

    # Параметр намеренно называется "kind", а не "format": "format" у DRF зарезервирован под
    # собственное content negotiation (?format=json и т.п.) и приводит к Http404 на рендеринге,
    # а не к нашей вьюхе, если передать туда незнакомое DRF значение вроде "xlsx".
    fmt = request.query_params.get("kind", "xlsx")
    overview = employer_services.organization_overview(organization, stream=stream, bundle=bundle)

    name_part = stream.code if stream else organization.name
    if bundle:
        name_part = f"{name_part}-{bundle.code}"
    if fmt == "pdf":
        body = export_services.build_pdf(overview)
        content_type = "application/pdf"
        filename = f"dashboard-{name_part}.pdf"
    elif fmt == "xlsx":
        body = export_services.build_xlsx(overview)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"dashboard-{name_part}.xlsx"
    else:
        return Response(
            {"detail": "Неизвестный формат экспорта, допустимо: pdf, xlsx (параметр kind)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    staff_profile = request.user.staff_profile
    export_services.record_export(
        organization=organization, stream=stream, kind=fmt, body=body, filename=filename, staff_profile=staff_profile
    )
    # ExportArtifact фиксирует сам файл, AuditEvent — действие (ТЗ FR-12.6). Это разные сущности,
    # поэтому пишутся обе; см. apps/identity/services.py.
    identity_services.record_event(
        action=identity_services.ACTION_EXPORT,
        actor=staff_profile,
        target_type="organization",
        target_id=organization.pk,
        metadata={"kind": fmt, "stream": stream.code if stream else None, "bundle": bundle.code if bundle else None},
    )

    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
