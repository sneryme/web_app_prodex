"""End-to-end API coverage for organization test bundles and participant progress."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client as AdminClient
from django.urls import reverse
from rest_framework.test import APIClient

from apps.assessments.models import AnswerOption, AnswerResponse, Question, QuestionnaireVersion, ScoringResult, TestBundle, TestBundleItem
from apps.organizations.models import Organization


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def bundle_flow_data(db):
    organization = Organization.objects.create(name="Bundle flow organization")
    questions = []
    versions = []
    for index, (code, indicator) in enumerate(
        (
            (QuestionnaireVersion.CODE_EQ5D, "eq5d_mobility"),
            (QuestionnaireVersion.CODE_STAI, "situational_anxiety"),
            (QuestionnaireVersion.CODE_HADS, "hads_anxiety"),
        ),
        start=1,
    ):
        version = QuestionnaireVersion.objects.create(
            code=code,
            version_label=f"bundle-flow-v{index}",
            is_active=True,
        )
        question = Question.objects.create(
            questionnaire_version=version,
            order=1,
            code=f"bundle_flow_{index}",
            text=f"Question {index}",
            indicator_code=indicator,
        )
        AnswerOption.objects.create(question=question, order=1, value=1, label="Option 1")
        AnswerOption.objects.create(question=question, order=2, value=2, label="Option 2")
        questions.append(question)
        versions.append(version)

    bundles = []
    for code, name in (("flow-a", "Flow bundle A"), ("flow-b", "Flow bundle B")):
        bundle = TestBundle.objects.create(code=code, name=name, is_active=True)
        for order, version in enumerate(versions, start=1):
            TestBundleItem.objects.create(bundle=bundle, order=order, questionnaire_version=version)
        bundles.append(bundle)
    return organization, bundles, questions


def _select_bundle(client, token, bundle):
    response = client.post(
        f"/api/participant/sessions/{token}/bundles/",
        {"bundle_id": bundle.pk},
        format="json",
    )
    assert response.status_code == 200
    return response.data


def _answer_stage(client, token, bundle, questions, stage, next_stage):
    responses = []
    for question in questions:
        response = client.post(
            f"/api/participant/sessions/{token}/answers/",
            {
                "bundle_id": bundle.pk,
                "stage": stage,
                "question_id": question.pk,
                "option_id": question.options.first().pk,
            },
            format="json",
        )
        assert response.status_code == 200
        responses.append(response)
    assert responses[-1].data["stage"] == next_stage


@pytest.mark.django_db
def test_django_admin_can_attach_and_detach_multiple_bundles(bundle_flow_data):
    organization, (bundle_a, bundle_b), _ = bundle_flow_data
    admin_user = get_user_model().objects.create_superuser(
        username="bundle-admin",
        email="bundle-admin@example.test",
        password="test-password",
    )
    admin_client = AdminClient()
    admin_client.force_login(admin_user)
    change_url = reverse("admin:organizations_organization_change", args=[organization.pk])

    form_data = {
        "name": organization.name,
        "legal_name": organization.legal_name,
        "entry_code": organization.entry_code,
        "test_bundles": [str(bundle_a.pk), str(bundle_b.pk)],
        "_save": "Save",
    }
    response = admin_client.post(change_url, form_data)
    assert response.status_code == 302
    organization.refresh_from_db()
    assert set(organization.test_bundles.values_list("pk", flat=True)) == {bundle_a.pk, bundle_b.pk}

    form_data["test_bundles"] = [str(bundle_a.pk)]
    response = admin_client.post(change_url, form_data)
    assert response.status_code == 302
    organization.refresh_from_db()
    assert list(organization.test_bundles.values_list("pk", flat=True)) == [bundle_a.pk]


@pytest.mark.django_db
def test_participant_can_complete_one_bundle_resume_and_keep_other_bundle_separate(client, bundle_flow_data):
    organization, (bundle_a, bundle_b), questions = bundle_flow_data
    organization.test_bundles.add(bundle_a, bundle_b)

    created = client.post(
        "/api/participant/sessions/",
        {"entry_code": organization.entry_code},
        format="json",
    )
    assert created.status_code == 201
    token = created.data["token"]
    assert {item["id"] for item in created.data["bundles"]} == {bundle_a.pk, bundle_b.pk}

    initial = _select_bundle(client, token, bundle_a)
    assert initial["stage"] == "baseline"
    assert initial["progress"] == {"answered": 0, "total": len(questions)}

    consent = client.post(
        f"/api/participant/sessions/{token}/consents/",
        {
            "bundle_id": bundle_a.pk,
            "consent_type": "data_processing",
            "text_version": "test-v1",
            "accepted": True,
        },
        format="json",
    )
    assert consent.status_code == 201

    _answer_stage(client, token, bundle_a, questions, "baseline", "followup")

    answer_url = f"/api/participant/sessions/{token}/answers/"
    last_question = questions[-1]
    last_answer = {
        "bundle_id": bundle_a.pk,
        "question_id": last_question.pk,
        "option_id": last_question.options.first().pk,
    }
    missing_stage = client.post(answer_url, last_answer, format="json")
    assert missing_stage.status_code == 400
    assert "stage" in missing_stage.data
    stale_answer = client.post(answer_url, {**last_answer, "stage": "baseline"}, format="json")
    assert stale_answer.status_code == 409
    assert stale_answer.data["code"] == "stage_mismatch"
    stored = AnswerResponse.objects.filter(token__token=token, bundle=bundle_a, question=last_question)
    assert list(stored.values_list("stage", "selected_option_id")) == [("baseline", last_answer["option_id"])]

    # Simulate the participant closing the browser and resuming with the token.
    resumed = client.get(f"/api/participant/sessions/{token}/")
    assert resumed.status_code == 200
    assert {item["id"]: item["status"] for item in resumed.data["bundles"]} == {
        bundle_a.pk: "in_progress",
        bundle_b.pk: "not_started",
    }
    followup = _select_bundle(client, token, bundle_a)
    assert followup["stage"] == "followup"
    assert followup["progress"] == {"answered": 0, "total": len(questions)}

    _answer_stage(client, token, bundle_a, questions, "followup", None)

    completed = client.get(f"/api/participant/sessions/{token}/")
    assert {item["id"]: item["status"] for item in completed.data["bundles"]} == {
        bundle_a.pk: "completed",
        bundle_b.pk: "not_started",
    }

    report = client.get(f"/api/participant/reports/{token}/?bundle_id={bundle_a.pk}")
    assert report.status_code == 200
    assert report.data["bundle_id"] == bundle_a.pk
    assert client.get(f"/api/participant/reports/{token}/?bundle_id={bundle_b.pk}").status_code == 404

    # A completed bundle exposes the report and refuses any attempt to submit again.
    completed_state = _select_bundle(client, token, bundle_a)
    assert completed_state["stage"] is None
    rejected = client.post(
        f"/api/participant/sessions/{token}/answers/",
        {
            "bundle_id": bundle_a.pk,
            "stage": "followup",
            "question_id": questions[0].pk,
            "option_id": questions[0].options.first().pk,
        },
        format="json",
    )
    assert rejected.status_code == 409

    # The same questions can be answered in another bundle without changing bundle A.
    second_bundle_state = _select_bundle(client, token, bundle_b)
    assert second_bundle_state["stage"] == "baseline"
    assert second_bundle_state["stage_status"] == "not_started"
    assert second_bundle_state["progress"] == {"answered": 0, "total": len(questions)}
    answer_b = client.post(
        f"/api/participant/sessions/{token}/answers/",
        {
            "bundle_id": bundle_b.pk,
            "stage": "baseline",
            "question_id": questions[0].pk,
            "option_id": questions[0].options.first().pk,
        },
        format="json",
    )
    assert answer_b.status_code == 200
    assert answer_b.data["progress"] == {"answered": 1, "total": len(questions)}
    assert client.get(f"/api/participant/reports/{token}/?bundle_id={bundle_b.pk}").status_code == 404

    answers_a = AnswerResponse.objects.filter(token__token=token, bundle=bundle_a)
    answers_b = AnswerResponse.objects.filter(token__token=token, bundle=bundle_b)
    assert answers_a.count() == len(questions) * 2
    assert answers_b.count() == 1
    assert ScoringResult.objects.filter(token__token=token, bundle=bundle_a).exists()
    assert not ScoringResult.objects.filter(token__token=token, bundle=bundle_b).exists()

    # Detaching a bundle hides it from new participants but preserves an existing participant's history.
    organization.test_bundles.remove(bundle_b)
    new_session = client.post(
        "/api/participant/sessions/",
        {"entry_code": organization.entry_code},
        format="json",
    )
    assert new_session.status_code == 201
    assert [item["id"] for item in new_session.data["bundles"]] == [bundle_a.pk]
    existing_session = client.get(f"/api/participant/sessions/{token}/")
    assert {item["id"] for item in existing_session.data["bundles"]} == {bundle_a.pk, bundle_b.pk}
