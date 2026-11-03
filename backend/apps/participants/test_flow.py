"""Сквозные тесты маршрута участника: FR-01 (вход), FR-03 (согласие), FR-04 (этапы), FR-06 (ответы)."""
import pytest
from rest_framework.test import APIClient

from apps.assessments.models import AnswerOption, AnswerResponse, Question, QuestionnaireVersion, TestBundle, TestBundleItem
from apps.organizations.models import Organization

from . import services
from .models import ParticipantToken


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="ООО Ромашка")


@pytest.fixture
def questionnaire(db):
    """Один активный вопрос на каждую из трёх методик — минимум, достаточный для проверки маршрута."""
    questions = []
    specs = [
        (QuestionnaireVersion.CODE_EQ5D, "mobility", "eq5d_mobility"),
        (QuestionnaireVersion.CODE_STAI, "situational_1", "situational_anxiety"),
        (QuestionnaireVersion.CODE_HADS, "anxiety_1", "hads_anxiety"),
    ]
    for code, question_code, indicator in specs:
        version = QuestionnaireVersion.objects.create(code=code, version_label="test-v1", is_active=True)
        question = Question.objects.create(
            questionnaire_version=version, order=1, code=question_code, text="…", indicator_code=indicator
        )
        AnswerOption.objects.create(question=question, order=1, value=1, label="Нет")
        AnswerOption.objects.create(question=question, order=2, value=2, label="Да")
        questions.append(question)
    return questions


@pytest.fixture
def client():
    return APIClient()


# --- FR-01: вход по коду ---------------------------------------------------

@pytest.mark.django_db
def test_create_session_with_valid_entry_code_issues_a_token(client, organization):
    response = client.post("/api/participant/sessions/", {"entry_code": organization.entry_code}, format="json")
    assert response.status_code == 201
    assert response.data["token"]
    assert ParticipantToken.objects.filter(token=response.data["token"]).exists()


@pytest.mark.django_db
def test_create_session_with_unknown_entry_code_returns_404_and_creates_nothing(client):
    response = client.post("/api/participant/sessions/", {"entry_code": "does-not-exist"}, format="json")
    assert response.status_code == 404
    assert ParticipantToken.objects.count() == 0


@pytest.mark.django_db
def test_resuming_a_valid_token_returns_its_current_state(client, organization):
    token = services.create_session(organization.entry_code)
    response = client.get(f"/api/participant/sessions/{token.token}/")
    assert response.status_code == 200
    assert response.data["token"] == token.token


@pytest.mark.django_db
def test_unknown_token_returns_404(client):
    response = client.get("/api/participant/sessions/does-not-exist/")
    assert response.status_code == 404


# --- FR-03: согласие ---------------------------------------------------------

@pytest.mark.django_db
def test_new_session_requires_consent(client, organization):
    token = services.create_session(organization.entry_code)
    state = client.get(f"/api/participant/sessions/{token.token}/").data
    assert state["consent_status"] == "required"


@pytest.mark.django_db
def test_answering_without_consent_is_rejected(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    response = client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": questionnaire[0].id, "option_id": questionnaire[0].options.first().id},
        format="json",
    )
    assert response.status_code == 403
    assert AnswerResponse.objects.count() == 0


@pytest.mark.django_db
def test_granting_consent_records_version_and_unlocks_answers(client, organization):
    token = services.create_session(organization.entry_code)
    response = client.post(
        f"/api/participant/sessions/{token.token}/consents/",
        {"consent_type": "data_processing", "text_version": "v1", "accepted": True},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["consent_status"] == "granted"
    assert token.consents.get().text_version == "v1"


@pytest.mark.django_db
def test_declining_consent_ends_the_route_without_saving_answers(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    client.post(
        f"/api/participant/sessions/{token.token}/consents/",
        {"consent_type": "data_processing", "text_version": "v1", "accepted": False},
        format="json",
    )
    state = client.get(f"/api/participant/sessions/{token.token}/").data
    assert state["consent_status"] == "declined"

    response = client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": questionnaire[0].id, "option_id": questionnaire[0].options.first().id},
        format="json",
    )
    assert response.status_code == 403
    assert AnswerResponse.objects.count() == 0


# --- FR-04 + FR-06: этапы и ответы ------------------------------------------

def _grant_consent(client, token):
    client.post(
        f"/api/participant/sessions/{token.token}/consents/",
        {"consent_type": "data_processing", "text_version": "v1", "accepted": True},
        format="json",
    )


@pytest.mark.django_db
def test_new_token_starts_on_baseline_stage(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)
    state = client.get(f"/api/participant/sessions/{token.token}/").data
    assert state["stage"] == "baseline"
    assert state["progress"] == {"answered": 0, "total": len(questionnaire)}
    # Ни одного ответа ещё нет — фронтенд должен показать стартовый экран этапа, а не вопросы
    # (StageIntroScreen.tsx), поэтому стадия помечена как "not_started".
    assert state["stage_status"] == "not_started"


@pytest.mark.django_db
def test_stage_status_switches_to_in_progress_after_the_first_answer(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": questionnaire[0].id, "option_id": questionnaire[0].options.first().id},
        format="json",
    )
    state = client.get(f"/api/participant/sessions/{token.token}/").data
    # Этап уже начат — перезагрузка должна вернуть прямо к вопросу (ТЗ FR-06.3/FR-06.4), а не на
    # стартовый экран заново.
    assert state["stage"] == "baseline"
    assert state["stage_status"] == "in_progress"


@pytest.mark.django_db
def test_completing_baseline_switches_to_followup_automatically(client, organization, questionnaire):
    # ТЗ FR-04.1/FR-04.2: без ручного выбора — только по факту завершённости.
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    for question in questionnaire:
        response = client.post(
            f"/api/participant/sessions/{token.token}/answers/",
            {"question_id": question.id, "option_id": question.options.first().id},
            format="json",
        )
        assert response.status_code == 200

    state = client.get(f"/api/participant/sessions/{token.token}/").data
    assert state["stage"] == "followup"
    assert state["progress"] == {"answered": 0, "total": len(questionnaire)}
    # Входной этап завершён, итоговый ещё не начат — снова стартовый экран, теперь перед followup.
    assert state["stage_status"] == "not_started"


@pytest.mark.django_db
def test_completing_both_stages_leaves_no_active_stage(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    for _ in range(2):  # baseline, затем followup
        for question in questionnaire:
            client.post(
                f"/api/participant/sessions/{token.token}/answers/",
                {"question_id": question.id, "option_id": question.options.first().id},
                format="json",
            )

    state = client.get(f"/api/participant/sessions/{token.token}/").data
    assert state["stage"] is None


@pytest.mark.django_db
def test_followup_cannot_be_reached_via_direct_answer_before_baseline_is_done(client, organization, questionnaire):
    # ТЗ FR-04.5: сервер сам определяет этап — прямой вызов API не может «перепрыгнуть» в followup.
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    first_question = questionnaire[0]
    client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": first_question.id, "option_id": first_question.options.first().id},
        format="json",
    )
    assert AnswerResponse.objects.filter(stage="followup").count() == 0
    assert services.current_stage(token) == "baseline"


@pytest.mark.django_db
def test_answer_submission_is_idempotent(client, organization, questionnaire):
    # ТЗ FR-06.6: повторная отправка того же вопроса не создаёт дублей и не портит счётчик прогресса.
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)
    question = questionnaire[0]
    options = list(question.options.all())

    client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": question.id, "option_id": options[0].id},
        format="json",
    )
    response = client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": question.id, "option_id": options[1].id},
        format="json",
    )

    assert AnswerResponse.objects.filter(token=token, stage="baseline", question=question).count() == 1
    assert response.data["progress"]["answered"] == 1
    stored = AnswerResponse.objects.get(token=token, stage="baseline", question=question)
    assert stored.selected_option_id == options[1].id  # последний ответ побеждает — можно передумать (FR-06.5)


@pytest.mark.django_db
def test_answering_unknown_question_is_rejected(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)
    response = client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": 999999, "option_id": None},
        format="json",
    )
    assert response.status_code == 400


# --- FR-07 + FR-08: scoring и персональный отчёт --------------------------

@pytest.fixture
def full_questionnaire(db):
    """Все 5 отчётных показателей плюс одно дополнительное измерение EQ-5D (профиль)."""
    specs = [
        (QuestionnaireVersion.CODE_EQ5D, "mobility", "eq5d_mobility"),
        (QuestionnaireVersion.CODE_EQ5D, "vas", "eq5d_vas"),
        (QuestionnaireVersion.CODE_STAI, "situational_1", "situational_anxiety"),
        (QuestionnaireVersion.CODE_STAI, "trait_1", "trait_anxiety"),
        (QuestionnaireVersion.CODE_HADS, "anxiety_1", "hads_anxiety"),
        (QuestionnaireVersion.CODE_HADS, "depression_1", "hads_depression"),
    ]
    versions = {}
    questions = []
    for code, question_code, indicator in specs:
        version = versions.get(code)
        if version is None:
            version = QuestionnaireVersion.objects.create(code=code, version_label="test-v1", is_active=True)
            versions[code] = version
        question = Question.objects.create(
            questionnaire_version=version,
            order=Question.objects.filter(questionnaire_version=version).count() + 1,
            code=question_code,
            text=f"вопрос {question_code}",
            indicator_code=indicator,
        )
        AnswerOption.objects.create(question=question, order=1, value=1, label="Совсем нет")
        AnswerOption.objects.create(question=question, order=2, value=4, label="Сильно")
        questions.append(question)
    return questions


def _complete_stage(client, token, questions, option_index):
    for question in questions:
        option = list(question.options.all())[option_index]
        client.post(
            f"/api/participant/sessions/{token.token}/answers/",
            {"question_id": question.id, "option_id": option.id},
            format="json",
        )


@pytest.mark.django_db
def test_report_endpoint_returns_404_before_both_stages_are_complete(client, organization, full_questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    response = client.get(f"/api/participant/reports/{token.token}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_report_endpoint_returns_404_for_unknown_token(client):
    response = client.get("/api/participant/reports/does-not-exist/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_report_endpoint_returns_five_cards_after_both_stages(client, organization, full_questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)

    _complete_stage(client, token, full_questionnaire, option_index=1)  # baseline: все «Сильно»
    _complete_stage(client, token, full_questionnaire, option_index=0)  # followup: все «Совсем нет»

    response = client.get(f"/api/participant/reports/{token.token}/")
    assert response.status_code == 200
    assert len(response.data["cards"]) == 5
    assert len(response.data["eq5d_profile"]) == 1  # eq5d_mobility — в профиле, не в карточках
    assert {c["indicator_code"] for c in response.data["cards"]} == {
        "eq5d_vas",
        "situational_anxiety",
        "trait_anxiety",
        "hads_anxiety",
        "hads_depression",
    }


@pytest.mark.django_db
def test_answering_after_both_stages_complete_returns_conflict(client, organization, questionnaire):
    token = services.create_session(organization.entry_code)
    _grant_consent(client, token)
    for _ in range(2):
        for question in questionnaire:
            client.post(
                f"/api/participant/sessions/{token.token}/answers/",
                {"question_id": question.id, "option_id": question.options.first().id},
                format="json",
            )

    response = client.post(
        f"/api/participant/sessions/{token.token}/answers/",
        {"question_id": questionnaire[0].id, "option_id": questionnaire[0].options.first().id},
        format="json",
    )
    assert response.status_code == 409


# --- Комплект тестов (TestBundle) --------------------------------------

@pytest.mark.django_db
def test_active_questions_follow_order_from_active_bundle():
    # Версии создаём в порядке HADS, EQ-5D, STAI, но в комплекте явно задаём другой порядок —
    # active_questions() должен следовать за комплектом, а не за порядком создания/кодом.
    hads = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    eq5d = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=True)
    stai = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_STAI, version_label="v1", is_active=True)
    for version, code in ((hads, "h1"), (eq5d, "e1"), (stai, "s1")):
        q = Question.objects.create(questionnaire_version=version, order=1, code=code, text="…", indicator_code=code)
        AnswerOption.objects.create(question=q, order=1, value=1, label="1")

    bundle = TestBundle.objects.create(code="custom", name="Другой порядок", is_active=True)
    TestBundleItem.objects.create(bundle=bundle, order=1, questionnaire_version=stai)
    TestBundleItem.objects.create(bundle=bundle, order=2, questionnaire_version=hads)
    TestBundleItem.objects.create(bundle=bundle, order=3, questionnaire_version=eq5d)

    questions = services.active_questions()
    assert [q.code for q in questions] == ["s1", "h1", "e1"]


@pytest.mark.django_db
def test_active_questions_falls_back_to_code_order_without_an_active_bundle():
    # Без активного комплекта — не падаем, а используем все активные версии, упорядоченные по коду.
    hads = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    eq5d = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=True)
    for version, code in ((hads, "h1"), (eq5d, "e1")):
        q = Question.objects.create(questionnaire_version=version, order=1, code=code, text="…", indicator_code=code)
        AnswerOption.objects.create(question=q, order=1, value=1, label="1")

    questions = services.active_questions()
    assert [q.code for q in questions] == ["e1", "h1"]  # "eq5d" < "hads" по алфавиту


@pytest.mark.django_db
def test_inactive_bundle_items_are_skipped():
    version = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=False)
    Question.objects.create(questionnaire_version=version, order=1, code="e1", text="…", indicator_code="e1")

    bundle = TestBundle.objects.create(code="custom", name="Комплект с неактивной методикой", is_active=True)
    TestBundleItem.objects.create(bundle=bundle, order=1, questionnaire_version=version)

    assert services.active_questions() == []
