from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import AnswerResponse, TestBundle
from apps.organizations.models import Organization
from apps.reporting.employer_services import organization_overview

from .models import ParticipantToken
from .services import active_questions


@pytest.mark.django_db
def test_cleanup_previews_and_preserves_current_history():
    output = StringIO()
    old_org = Organization.objects.create(name="Старая организация")
    current_org = Organization.objects.create(name="Перешла на ИИПБ")
    call_command("seed_real_questionnaires", stdout=output)
    old_bundle = TestBundle.objects.get(code="prodex-v1")
    old_org.test_bundles.add(old_bundle)
    current_org.test_bundles.add(old_bundle)
    old_question = active_questions(old_bundle)[0]
    old_token = ParticipantToken.objects.create(organization=old_org)
    retained = ParticipantToken.objects.create(organization=current_org)
    for token in (old_token, retained):
        AnswerResponse.objects.create(token=token, bundle=old_bundle, question=old_question, stage="baseline")

    call_command("seed_iipb_methodology", stdout=output)
    current_bundle = TestBundle.objects.get(code=METHODOLOGY)
    new_answer = AnswerResponse.objects.create(
        token=retained, bundle=current_bundle, question=active_questions(current_bundle)[0], stage="baseline",
    )
    call_command("purge_legacy_methodologies", stdout=output)
    assert "Предварительный просмотр" in output.getvalue()
    assert ParticipantToken.objects.filter(pk=old_token.pk).exists()
    assert TestBundle.objects.filter(pk=old_bundle.pk).exists()
    with pytest.raises(CommandError, match="ИИПБ"):
        call_command("purge_legacy_methodologies", apply=True, organization_id=[current_org.pk], stdout=output)

    call_command("purge_legacy_methodologies", apply=True, organization_id=[old_org.pk], stdout=output)
    assert list(TestBundle.objects.values_list("code", flat=True)) == [METHODOLOGY]
    assert not Organization.objects.filter(pk=old_org.pk).exists()
    assert ParticipantToken.objects.filter(pk=retained.pk).exists()
    assert list(retained.answers.values_list("pk", flat=True)) == [new_answer.pk]


@pytest.mark.django_db
def test_demo_seeds_dashboard_and_separate_participant(monkeypatch):
    monkeypatch.setenv("IIPB_DEMO_STAFF_PASSWORD", "local-test-only")
    output = StringIO()
    call_command("seed_iipb_methodology", stdout=output)
    call_command("seed_iipb_demo", test_participant=True, stdout=output)
    call_command("seed_iipb_demo", stdout=output)

    organization = Organization.objects.get(entry_code="iipb-presentation", is_demo=True)
    staff = authenticate(username="iipb_demo", password="local-test-only")
    assert staff.staff_profile.organization == organization
    assert list(organization.test_bundles.values_list("code", flat=True)) == [METHODOLOGY]
    assert organization.participant_tokens.filter(is_test=False).count() == 11
    test_participant = organization.participant_tokens.get(is_test=True)
    assert test_participant.iipb_results.get(stage="baseline").index == 66
    assert test_participant.consents.count() == 0
    main = organization_overview(organization, stream=organization.streams.get(code="iipb-demo-main"))
    pilot = organization_overview(organization, stream=organization.streams.get(code="iipb-demo-pilot"))
    assert main["iipb"]["trend"]["paired_count"] == 8
    assert pilot["iipb"]["trend"] == {"paired_count": 3, "is_suppressed": True}
