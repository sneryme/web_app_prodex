"""Тесты операционного контура PRODEX Admin (ТЗ FR-11)."""
import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assessments.models import AnswerResponse, Question, QuestionnaireVersion, ScoringResult
from apps.identity.models import StaffProfile
from apps.organizations.models import License, Organization, Stream
from apps.participants.models import ParticipantToken


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
def test_anonymous_request_is_rejected():
    response = APIClient().get("/api/prodex/clients/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_org_admin_is_denied_access(org_a):
    """ТЗ FR-11.1: администратор организации получает отказ, а не данные другой роли."""
    client = _staff_client(StaffProfile.ROLE_ORG_ADMIN, org_a)

    for path in ("/api/prodex/clients/", "/api/prodex/licenses/", "/api/prodex/operations/"):
        response = client.get(path)
        assert response.status_code == 403, path


@pytest.mark.django_db
def test_prodex_admin_sees_all_clients_with_license_status(org_a, org_b):
    """ТЗ FR-11.2/FR-11.3."""
    today = timezone.localdate()
    License.objects.create(organization=org_a, starts_at=today, ends_at=today + datetime.timedelta(days=365), status=License.STATUS_ACTIVE)
    License.objects.create(
        organization=org_b, starts_at=today - datetime.timedelta(days=400), ends_at=today - datetime.timedelta(days=30), status=License.STATUS_EXPIRED
    )
    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)

    response = client.get("/api/prodex/clients/")
    assert response.status_code == 200
    by_name = {row["name"]: row for row in response.data}
    assert by_name["ООО Ромашка"]["license"]["status"] == License.STATUS_ACTIVE
    assert by_name["ООО Ромашка"]["license"]["is_expired"] is False
    assert by_name["ООО Вектор Плюс"]["license"]["status"] == License.STATUS_EXPIRED
    assert by_name["ООО Вектор Плюс"]["license"]["is_expired"] is True


@pytest.mark.django_db
def test_clients_filter_by_search_and_license_status(org_a, org_b):
    today = timezone.localdate()
    License.objects.create(organization=org_a, starts_at=today, ends_at=today + datetime.timedelta(days=365), status=License.STATUS_ACTIVE)
    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)

    response = client.get("/api/prodex/clients/?search=Ромашка")
    assert [row["name"] for row in response.data] == ["ООО Ромашка"]

    response = client.get("/api/prodex/clients/?license_status=active")
    assert [row["name"] for row in response.data] == ["ООО Ромашка"]  # у org_b лицензии нет вовсе


@pytest.mark.django_db
def test_licenses_endpoint_lists_organization_for_each_license(org_a):
    today = timezone.localdate()
    License.objects.create(organization=org_a, starts_at=today, ends_at=today + datetime.timedelta(days=365))
    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)

    response = client.get("/api/prodex/licenses/")
    assert response.status_code == 200
    assert response.data[0]["organization"]["id"] == org_a.id


@pytest.mark.django_db
def test_operations_overview_has_no_psychological_fields(org_a):
    """ТЗ FR-11.4/FR-11.5: видны потоки/completion/активность/ошибки, индивидуальных и
    психологических данных (индикаторы, зоны, баллы) нет вовсе."""
    stream = Stream.objects.create(organization=org_a, code="s1")
    token = ParticipantToken.objects.create(
        organization=org_a, stream=stream, baseline_status=ParticipantToken.PROGRESS_COMPLETED
    )
    version = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    question = Question.objects.create(questionnaire_version=version, order=1, code="q1", text="?", indicator_code="hads_anxiety")
    AnswerResponse.objects.create(token=token, stage="baseline", question=question, raw_value="5")
    # Намеренно без ScoringResult — это и есть "ошибка подсчёта" (например, смешанная версия).

    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)
    response = client.get("/api/prodex/operations/")

    assert response.status_code == 200
    assert response.data["organizations_count"] == 1
    assert response.data["completion"]["baseline_completed"] == 1
    assert response.data["errors"]["unscored_answer_groups"] == 1
    serialized = str(response.data)
    for forbidden in ["indicator_code", "zone", "raw_score", "hads_anxiety"]:
        assert forbidden not in serialized


@pytest.mark.django_db
def test_operations_counts_are_not_affected_by_scored_answers(org_a):
    """Контрольный случай для предыдущего теста: если ScoringResult есть, ошибок не считаем."""
    stream = Stream.objects.create(organization=org_a, code="s1")
    token = ParticipantToken.objects.create(organization=org_a, stream=stream)
    version = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    question = Question.objects.create(questionnaire_version=version, order=1, code="q1", text="?", indicator_code="hads_anxiety")
    AnswerResponse.objects.create(token=token, stage="baseline", question=question, raw_value="5")
    ScoringResult.objects.create(
        token=token, stage="baseline", indicator_code="hads_anxiety", raw_score=5, questionnaire_version=version
    )

    client = _staff_client(StaffProfile.ROLE_PRODEX_ADMIN)
    response = client.get("/api/prodex/operations/")

    assert response.data["errors"]["unscored_answer_groups"] == 0
