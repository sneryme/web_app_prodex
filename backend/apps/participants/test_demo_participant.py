"""Тестовый участник обходит только ожидание, сохраняя согласия и полноту замера."""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import AnswerResponse, IIPBResult, TestBundle
from apps.assessments.scoring import compute_scores_for_stage
from apps.assessments.test_iipb import AFTER, BEFORE, complete_stage
from apps.organizations.models import Organization, Stream
from apps.reporting.employer_services import compare_periods, compare_streams, list_streams, organization_overview
from apps.reporting.iipb_services import iipb_overview
from apps.participants.management.commands.create_test_participant import TEST_ORGANIZATION_CODE
from apps.participants.models import ParticipantToken
from apps.participants import services


@pytest.fixture
def setup(db):
    organization = Organization.objects.create(name="Обычные участники для проверки")
    call_command("seed_iipb_methodology", stdout=StringIO())
    return organization, TestBundle.objects.get(code=METHODOLOGY), APIClient()


def create_demo():
    output = StringIO()
    call_command("create_test_participant", stdout=output)
    return ParticipantToken.objects.filter(is_test=True).latest("pk"), output.getvalue()


def grant_consents(client, token, bundle):
    for consent_type in ("informed_notice", "data_processing"):
        response = client.post(
            f"/api/participant/sessions/{token.token}/consents/",
            {"bundle_id": bundle.pk, "consent_type": consent_type, "text_version": METHODOLOGY, "accepted": True},
            format="json",
        )
        assert response.status_code == 201
    assert response.data["consent_status"] == "granted"
    return response.data


def first_followup_answer(bundle):
    question = services.active_questions(bundle)[0]
    return {"bundle_id": bundle.pk, "stage": "followup", "question_id": question.pk, "option_id": question.options.first().pk}


def test_command_creates_current_synthetic_baseline_without_recording_consent(setup):
    _, bundle, client = setup
    started = timezone.now()
    token, output = create_demo()
    baseline = IIPBResult.objects.get(token=token, bundle=bundle, stage="baseline")

    assert token.is_test
    assert token.organization.entry_code == TEST_ORGANIZATION_CODE
    assert token.organization != setup[0]
    assert started <= token.created_at <= baseline.measured_at <= timezone.now()
    assert baseline.index == 66
    assert baseline.payload["inputs"] == BEFORE
    assert token.answers.filter(bundle=bundle, stage="baseline").count() == 60
    assert not token.answers.filter(stage="followup").exists()
    assert token.baseline_status == ParticipantToken.PROGRESS_COMPLETED
    assert token.consents.count() == 0
    assert f"?token={token.token}" in output

    state = services.session_state(token, bundle)
    assert state["stage"] == "followup"
    assert state["consent_status"] == "required"
    assert state["baseline_result"] is None
    assert state["questions"] == []
    assert client.post(f"/api/participant/sessions/{token.token}/answers/", first_followup_answer(bundle), format="json").status_code == 403
    assert client.get(f"/api/participant/reports/{token.token}/?bundle_id={bundle.pk}").status_code == 403


def test_demo_can_complete_followup_immediately_after_confirming_both_consents(setup):
    _, bundle, client = setup
    token, _ = create_demo()
    baseline = IIPBResult.objects.get(token=token, stage="baseline")
    state = grant_consents(client, token, bundle)
    assert state["is_test"] is True
    assert state["followup_locked"] is False
    assert len(state["questions"]) == 60
    assert state["baseline_result"]["index"] == 66
    assert services.followup_available_at(token, bundle) == baseline.measured_at

    response = client.post(f"/api/participant/sessions/{token.token}/answers/", first_followup_answer(bundle), format="json")
    assert response.status_code == 200
    assert response.data["stage"] == "followup"
    assert complete_stage(token, bundle, AFTER, stage="followup")["stage"] is None
    after = IIPBResult.objects.get(token=token, stage="followup")
    assert after.measured_at - baseline.measured_at < timedelta(days=7)
    assert after.index == 79
    response = client.get(f"/api/participant/reports/{token.token}/?bundle_id={bundle.pk}")
    assert response.status_code == 200
    assert response.data["iipb"]["dynamics"]["delta_pp"] == 13


def test_normal_participant_still_waits_seven_days(setup):
    organization, bundle, client = setup
    token = ParticipantToken.objects.create(organization=organization)
    grant_consents(client, token, bundle)
    state = complete_stage(token, bundle, BEFORE, stage="baseline")
    baseline = IIPBResult.objects.get(token=token, stage="baseline")

    assert token.is_test is False
    assert services.followup_available_at(token, bundle) == baseline.measured_at + timedelta(days=7)
    assert state["followup_locked"] is True
    assert state["questions"] == []
    response = client.post(f"/api/participant/sessions/{token.token}/answers/", first_followup_answer(bundle), format="json")
    assert response.status_code == 409
    assert not token.answers.filter(stage="followup").exists()


def test_public_session_creation_cannot_enable_test_access(setup):
    organization, _, client = setup
    response = client.post(
        "/api/participant/sessions/",
        {"entry_code": organization.entry_code, "is_test": True},
        format="json",
    )
    assert response.status_code == 201
    assert ParticipantToken.objects.get(token=response.data["token"]).is_test is False


def test_repeated_command_creates_a_new_participant_without_resetting_existing_history(setup):
    _, bundle, _ = setup
    first, _ = create_demo()
    snapshot = IIPBResult.objects.get(token=first, bundle=bundle)
    payload, measured_at = snapshot.payload, snapshot.measured_at
    answer_ids = set(first.answers.values_list("pk", flat=True))
    second, _ = create_demo()

    assert first.pk != second.pk and first.token != second.token
    assert first.organization_id == second.organization_id
    assert first.stream_id == second.stream_id
    assert ParticipantToken.objects.filter(is_test=True).count() == 2
    first.refresh_from_db()
    snapshot.refresh_from_db()
    assert snapshot.payload == payload
    assert snapshot.measured_at == measured_at
    assert set(first.answers.values_list("pk", flat=True)) == answer_ids
    assert not first.consents.exists()


@pytest.mark.parametrize("missing_snapshot", [False, True])
def test_test_access_never_skips_required_baseline(setup, missing_snapshot):
    organization, bundle, client = setup
    if missing_snapshot:
        token, _ = create_demo()
        token.iipb_results.all().delete()
    else:
        token = ParticipantToken.objects.create(organization=organization, is_test=True)
    state = grant_consents(client, token, bundle)

    assert services.followup_available_at(token, bundle) is None
    assert not token.answers.filter(stage="followup").exists()
    if missing_snapshot:
        assert state["stage"] == "followup"
        assert state["followup_locked"] is True
        assert state["questions"] == []
        response = client.post(f"/api/participant/sessions/{token.token}/answers/", first_followup_answer(bundle), format="json")
        assert response.status_code == 409
    else:
        assert state["stage"] == "baseline"
        assert state["baseline_result"] is None


def test_test_participant_cannot_raise_real_group_above_publication_threshold(setup):
    _, bundle, _ = setup
    demo, _ = create_demo()
    organization, stream = demo.organization, demo.stream
    baseline_answers = list(demo.answers.select_related("question", "selected_option"))
    real_tokens = [ParticipantToken.objects.create(organization=organization, stream=stream) for _ in range(4)]
    for token in [demo, *real_tokens]:
        for stage in ("baseline", "followup"):
            if token == demo and stage == "baseline":
                continue
            AnswerResponse.objects.bulk_create([
                AnswerResponse(token=token, bundle=bundle, stage=stage, question=answer.question,
                               selected_option=answer.selected_option, raw_value=answer.raw_value)
                for answer in baseline_answers
            ])
            compute_scores_for_stage(token, stage, bundle)

    tokens = ParticipantToken.objects.filter(organization=organization)
    assert tokens.count() == 5
    iipb = iipb_overview(tokens, bundle, 5)
    assert iipb["baseline"] == {"participant_count": 4, "is_suppressed": True}
    assert iipb["followup"] == {"participant_count": 4, "is_suppressed": True}
    assert iipb["trend"] == {"paired_count": 4, "is_suppressed": True}

    def assert_suppressed(overview):
        assert overview["coverage"]["participants"] == 4
        assert overview["completion"] == {"baseline_completed": 4, "followup_completed": 4}
        for indicator in overview["indicators"]:
            assert indicator["baseline"] == {"participant_count": 4, "is_suppressed": True}
            assert indicator["followup"] == {"participant_count": 4, "is_suppressed": True}
            assert indicator["trend"] == {"paired_count": 4, "is_suppressed": True}
        assert overview["iipb"]["baseline"]["is_suppressed"] is True

    assert_suppressed(organization_overview(organization, stream=stream, bundle=bundle))
    assert list_streams(organization)[0]["participant_count"] == 4
    other_stream = Stream.objects.create(organization=organization, code="empty-comparison", name="Пустой поток")
    groups = compare_streams(organization, [stream.pk, other_stream.pk], bundle=bundle)
    assert_suppressed(next(g["overview"] for g in groups if g["key"] == f"stream-{stream.pk}"))
    today = timezone.localdate()
    periods = [
        {"from": today, "to": today, "label": "Сегодня"},
        {"from": today + timedelta(days=1), "to": today + timedelta(days=1), "label": "Завтра"},
    ]
    assert_suppressed(compare_periods(organization, periods, bundle=bundle)[0]["overview"])
