import pytest
from django.db import IntegrityError

from apps.organizations.models import Organization

from .models import ConsentRecord, ParticipantToken, StageProgress


@pytest.mark.django_db
def test_participant_token_is_generated_automatically_and_unique():
    org = Organization.objects.create(name="ООО Ромашка")
    token_a = ParticipantToken.objects.create(organization=org)
    token_b = ParticipantToken.objects.create(organization=org)
    assert token_a.token
    assert token_a.token != token_b.token


@pytest.mark.django_db
def test_participant_token_never_stores_direct_identifiers():
    # Охранный тест на PROJECT_RULES №3: у модели токена нет полей вроде ФИО/телефона/e-mail.
    field_names = {f.name for f in ParticipantToken._meta.get_fields()}
    forbidden = {"full_name", "name", "phone", "email", "employee_id"}
    assert field_names.isdisjoint(forbidden)


@pytest.mark.django_db
def test_stage_progress_is_unique_per_token_and_stage():
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    StageProgress.objects.create(token=token, stage=StageProgress.STAGE_BASELINE)
    with pytest.raises(IntegrityError):
        StageProgress.objects.create(token=token, stage=StageProgress.STAGE_BASELINE)


@pytest.mark.django_db
def test_consent_record_keeps_type_and_version_as_a_journal_entry():
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    consent = ConsentRecord.objects.create(
        token=token, consent_type=ConsentRecord.TYPE_DATA_PROCESSING, text_version="v1", accepted=True
    )
    assert consent.accepted_at is not None
    assert consent.text_version == "v1"
