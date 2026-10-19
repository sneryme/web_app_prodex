import pytest

from apps.organizations.models import Organization

from .models import ConsentRecord, ParticipantToken


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
def test_fresh_token_starts_with_both_stages_not_started_and_no_report():
    # Прогресс по этапам и отчёт — поля на самом токене (бывшие StageProgress/PersonalReportSnapshot),
    # уникальность "один статус на этап" теперь гарантирована структурой таблицы, а не constraint'ом.
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    assert token.baseline_status == ParticipantToken.PROGRESS_NOT_STARTED
    assert token.followup_status == ParticipantToken.PROGRESS_NOT_STARTED
    assert token.baseline_started_at is None
    assert token.report_payload is None
    assert token.report_generated_at is None


@pytest.mark.django_db
def test_consent_record_keeps_type_and_version_as_a_journal_entry():
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    consent = ConsentRecord.objects.create(
        token=token, consent_type=ConsentRecord.TYPE_DATA_PROCESSING, text_version="v1", accepted=True
    )
    assert consent.accepted_at is not None
    assert consent.text_version == "v1"
