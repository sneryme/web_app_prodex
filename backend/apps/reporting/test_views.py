"""Тесты входа и разграничения доступа к API дашборда работодателя (ТЗ FR-09.1/FR-12-lite)."""
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.assessments.models import AnswerResponse, ScoringResult, TestBundle
from apps.identity.models import AuditEvent, StaffProfile
from apps.organizations.models import Organization, Stream
from apps.participants.models import ParticipantToken
from apps.participants.services import active_questions
from apps.reporting.models import ExportArtifact


@pytest.fixture
def org_a(db):
    return Organization.objects.create(name="ООО Ромашка")


@pytest.fixture
def org_b(db):
    return Organization.objects.create(name="ООО Вектор Плюс")


def _staff_client(role, organization=None):
    user = User.objects.create_user(username=f"user-{role}-{organization}", password="secret-pass")
    StaffProfile.objects.create(user=user, role=role, organization=organization)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_anonymous_request_is_rejected(org_a):
    client = APIClient()
    response = client.get("/api/employer/organizations/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_org_admin_sees_only_their_own_organization(org_a, org_b):
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    response = client.get("/api/employer/organizations/")
    assert response.status_code == 200
    assert [org["id"] for org in response.data] == [org_a.id]


@pytest.mark.django_db
def test_org_admin_cannot_reach_another_organizations_overview(org_a, org_b):
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    response = client.get(f"/api/employer/organizations/{org_b.id}/overview/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_prodex_admin_sees_all_organizations(org_a, org_b):
    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)

    response = client.get("/api/employer/organizations/")
    assert response.status_code == 200
    assert {org["id"] for org in response.data} == {org_a.id, org_b.id}


@pytest.mark.django_db
def test_own_organization_overview_is_reachable(org_a):
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    response = client.get(f"/api/employer/organizations/{org_a.id}/overview/")
    assert response.status_code == 200
    assert response.data["organization"]["id"] == org_a.id


@pytest.mark.django_db
@pytest.mark.parametrize(("seed_command", "bundle_code"), [
    ("seed_iipb_methodology", "iipb-0.1"),
    ("seed_real_questionnaires", "prodex-v1"),
])
def test_seeded_demo_streams_report_both_stages_for_selected_bundle(seed_command, bundle_code):
    output = StringIO()
    call_command("seed_demo_organization", stdout=output)
    call_command(seed_command, stdout=output)
    bundle = TestBundle.objects.get(code=bundle_code)
    demo_org = Organization.objects.get(entry_code="demo-entry-code")
    existing_stream = Stream.objects.create(organization=demo_org, code="2026-H2")
    old_token = ParticipantToken.objects.create(organization=demo_org, stream=existing_stream)
    question = active_questions(bundle)[0]
    old_answer = AnswerResponse.objects.create(
        token=old_token, stage="baseline", question=question, selected_option=question.options.first()
    )

    call_command("seed_employer_demo_streams", bundle=bundle_code, stdout=output)
    call_command("seed_employer_demo_streams", bundle=bundle_code, stdout=output)

    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)
    for stream in Stream.objects.filter(code__in=["2026-H2", "2026-pilot"]):
        count = 8 if stream.code == "2026-H2" else 3
        assert stream.organization.test_bundles.filter(pk=bundle.pk).exists()
        response = client.get(
            f"/api/employer/organizations/{stream.organization_id}/overview/",
            {"stream": stream.pk, "bundle": bundle.pk},
        )
        assert response.status_code == 200
        overview = response.data
        assert overview["bundle"]["code"] == bundle_code
        assert overview["coverage"] == {"participants": count}
        assert overview["completion"] == {"baseline_completed": count, "followup_completed": count}
        aggregate = overview["iipb"] if bundle_code == "iipb-0.1" else overview["indicators"][0]
        for stage in ("baseline", "followup"):
            assert aggregate[stage]["participant_count"] == count
            assert aggregate[stage]["is_suppressed"] == (count < 5)
            assert ("mean" in aggregate[stage]) == (count >= 5)
        assert aggregate["trend"]["paired_count"] == count
        assert aggregate["trend"]["is_suppressed"] == (count < 5)

    assert Stream.objects.filter(code__in=["2026-H2", "2026-pilot"]).count() == 2
    old_answer.refresh_from_db()
    assert old_answer.bundle_id is None
    if bundle_code == "iipb-0.1":
        seeded_token = ParticipantToken.objects.filter(iipb_results__bundle=bundle).first()
        snapshots = dict(seeded_token.iipb_results.values_list("stage", "measured_at"))
        assert snapshots["followup"] - snapshots["baseline"] == timedelta(days=7)


@pytest.mark.django_db
@pytest.mark.parametrize("fmt,content_type", [("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ("pdf", "application/pdf")])
def test_export_returns_the_requested_file_and_records_an_artifact(org_a, fmt, content_type):
    stream = Stream.objects.create(organization=org_a, code="s1", min_group_size=1)
    token = ParticipantToken.objects.create(organization=org_a, stream=stream)
    ScoringResult.objects.create(token=token, stage="baseline", indicator_code="hads_anxiety", raw_score=7, interpretation_zone="норма")
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    response = client.get(f"/api/employer/organizations/{org_a.id}/export/?kind={fmt}&stream={stream.id}")

    assert response.status_code == 200
    assert response["Content-Type"] == content_type
    assert len(response.content) > 0
    assert ExportArtifact.objects.filter(organization=org_a, stream=stream, kind=fmt).exists()
    # ТЗ FR-12.6: артефакт фиксирует файл, журнал — действие. Нужны обе записи.
    event = AuditEvent.objects.get(action="employer.export")
    assert event.target_id == str(org_a.pk)
    assert event.metadata == {"kind": fmt, "stream": stream.code, "bundle": None}


@pytest.mark.django_db
def test_export_rejects_an_unknown_format(org_a):
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    response = client.get(f"/api/employer/organizations/{org_a.id}/export/?kind=doc")

    assert response.status_code == 400
