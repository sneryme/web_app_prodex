"""Сквозные тесты бизнес-логики маршрута участника (services.py) с вопросом без вариантов
ответа (EQ-5D VAS) — до этого submit_answer проверялся только через модельные/scoring-тесты
с готовыми ScoringResult, без реального вызова через слой сервисов."""
import pytest

from apps.assessments.models import AnswerOption, Question, QuestionnaireVersion
from apps.organizations.models import Organization

from .models import ParticipantToken
from .services import InvalidAnswerValue, UnknownQuestion, record_consent, submit_answer


@pytest.fixture
def numeric_question(db):
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=True)
    # Второй вопрос — чтобы этап не завершался сразу после единственного ответа (иначе
    # current_stage() уже переключится на followup к моменту сборки session_state()).
    Question.objects.create(questionnaire_version=qv, order=2, code="mobility", text="…", indicator_code="eq5d_mobility")
    return Question.objects.create(questionnaire_version=qv, order=1, code="vas", text="…", indicator_code="eq5d_vas")


@pytest.fixture
def token(db, numeric_question):
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    record_consent(token, "data_processing", "v1", True)
    return token


@pytest.mark.django_db
def test_free_numeric_answer_is_saved_as_raw_value(token, numeric_question):
    state = submit_answer(token, question_id=numeric_question.id, option_id=None, raw_value="72")
    assert state["questions"][0]["answer"] == {"option_id": None, "raw_value": "72"}


@pytest.mark.django_db
def test_free_numeric_answer_rejects_out_of_range_value(token, numeric_question):
    with pytest.raises(InvalidAnswerValue):
        submit_answer(token, question_id=numeric_question.id, option_id=None, raw_value="150")


@pytest.mark.django_db
def test_free_numeric_answer_rejects_non_numeric_value(token, numeric_question):
    with pytest.raises(InvalidAnswerValue):
        submit_answer(token, question_id=numeric_question.id, option_id=None, raw_value="много")


@pytest.mark.django_db
def test_free_numeric_question_rejects_an_option_id(token, numeric_question):
    # У вопроса нет вариантов ответа — option_id здесь всегда не относится к нему.
    with pytest.raises(UnknownQuestion):
        submit_answer(token, question_id=numeric_question.id, option_id=999, raw_value="")


@pytest.mark.django_db
def test_option_based_question_requires_an_option_id(db):
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    record_consent(token, "data_processing", "v1", True)
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    question = Question.objects.create(questionnaire_version=qv, order=1, code="hads_1", text="…", indicator_code="hads_anxiety")
    AnswerOption.objects.create(question=question, order=1, value=3, label="Всё время")

    with pytest.raises(UnknownQuestion):
        submit_answer(token, question_id=question.id, option_id=None, raw_value="")
