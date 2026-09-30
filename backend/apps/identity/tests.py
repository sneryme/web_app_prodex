import pytest
from django.contrib.auth.models import User

from apps.organizations.models import Organization

from .models import AuditEvent, StaffProfile


@pytest.mark.django_db
def test_coordinator_and_hr_are_the_only_org_scoped_roles():
    # ТЗ FR-12: координатор/HR видят агрегаты своей организации, остальные роли — операционный контур PRODEX.
    assert StaffProfile.ORG_SCOPED_ROLES == {StaffProfile.ROLE_COORDINATOR, StaffProfile.ROLE_HR}


@pytest.mark.django_db
def test_audit_event_survives_staff_profile_deletion():
    # ТЗ FR-12.6: критичные действия должны остаться в журнале, даже если сотрудник впоследствии удалён.
    org = Organization.objects.create(name="ООО Ромашка")
    user = User.objects.create(username="hr1")
    staff = StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_HR, organization=org)
    event = AuditEvent.objects.create(actor=staff, action="export.pdf", target_type="stream", target_id="1")

    staff.delete()
    event.refresh_from_db()
    assert event.actor is None
    assert event.action == "export.pdf"
