import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.organizations.models import Organization

from .models import AuditEvent, StaffProfile


@pytest.mark.django_db
def test_org_admin_is_the_only_org_scoped_role():
    # Положение о ролях, п. 2: администратор организации ограничен своим юрлицом, администратор
    # PRODEX — нет. Участник в StaffProfile не входит: у него нет логина (его роль — ParticipantToken).
    assert StaffProfile.ORG_SCOPED_ROLES == {StaffProfile.ROLE_ORG_ADMIN}
    assert [role for role, _ in StaffProfile.ROLE_CHOICES] == [
        StaffProfile.ROLE_ORG_ADMIN,
        StaffProfile.ROLE_PRODEX_ADMIN,
    ]


@pytest.mark.django_db
def test_audit_event_survives_staff_profile_deletion():
    # ТЗ FR-12.6: критичные действия должны остаться в журнале, даже если сотрудник впоследствии удалён.
    org = Organization.objects.create(name="ООО Ромашка")
    user = User.objects.create(username="hr1")
    staff = StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_ORG_ADMIN, organization=org)
    event = AuditEvent.objects.create(actor=staff, action="export.pdf", target_type="stream", target_id="1")

    staff.delete()
    event.refresh_from_db()
    assert event.actor is None
    assert event.action == "export.pdf"


@pytest.mark.django_db
def test_login_issues_token_only_for_users_with_a_staff_profile():
    # ТЗ FR-12-lite: обычный django User без StaffProfile — это не сотрудник, доступа быть не должно.
    org = Organization.objects.create(name="ООО Ромашка")
    user = User.objects.create_user(username="hr1", password="secret-pass")
    StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_ORG_ADMIN, organization=org)
    User.objects.create_user(username="no_profile", password="secret-pass")

    client = APIClient()

    ok = client.post("/api/identity/login/", {"username": "hr1", "password": "secret-pass"}, format="json")
    assert ok.status_code == 200
    assert ok.data["role"] == StaffProfile.ROLE_ORG_ADMIN
    assert ok.data["organization"] == {"id": org.id, "name": org.name}
    assert Token.objects.filter(user=user, key=ok.data["token"]).exists()

    wrong_password = client.post("/api/identity/login/", {"username": "hr1", "password": "nope"}, format="json")
    assert wrong_password.status_code == 401

    no_profile = client.post(
        "/api/identity/login/", {"username": "no_profile", "password": "secret-pass"}, format="json"
    )
    assert no_profile.status_code == 403


@pytest.mark.django_db
def test_logout_revokes_the_token():
    user = User.objects.create_user(username="hr1", password="secret-pass")
    StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_ORG_ADMIN)
    token = Token.objects.create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    response = client.post("/api/identity/logout/")

    assert response.status_code == 204
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_logout_and_failed_attempts_are_journalled_without_the_password():
    """ТЗ FR-12.6 / Положение о ролях, п. 5.3: входы и выходы попадают в журнал.

    Неудачная попытка тоже журналируется, но без сотрудника (его ещё нет) — и ни при каких
    условиях в журнал не попадает пароль.
    """
    org = Organization.objects.create(name="ООО Ромашка")
    user = User.objects.create_user(username="hr1", password="secret-pass")
    profile = StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_ORG_ADMIN, organization=org)
    client = APIClient()

    client.post("/api/identity/login/", {"username": "hr1", "password": "wrong"}, format="json")
    failed = AuditEvent.objects.get(action="staff.login_failed")
    assert failed.actor is None
    assert failed.metadata["username"] == "hr1"
    assert "secret-pass" not in str(failed.metadata) and "wrong" not in str(failed.metadata)

    ok = client.post("/api/identity/login/", {"username": "hr1", "password": "secret-pass"}, format="json")
    assert AuditEvent.objects.get(action="staff.login").actor == profile

    client.credentials(HTTP_AUTHORIZATION=f"Token {ok.data['token']}")
    client.post("/api/identity/logout/")
    assert AuditEvent.objects.get(action="staff.logout").actor == profile


@pytest.mark.django_db
def test_audit_journal_cannot_be_appended_or_deleted_through_the_admin():
    # Журнал, в котором можно дописать или стереть строку, не выполняет своей задачи.
    from django.contrib.admin.sites import AdminSite

    from .admin import AuditEventAdmin

    admin_instance = AuditEventAdmin(AuditEvent, AdminSite())
    assert admin_instance.has_add_permission(None) is False
    assert admin_instance.has_delete_permission(None) is False
