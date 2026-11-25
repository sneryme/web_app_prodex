import pytest
from django.db import IntegrityError

from apps.organizations.models import Organization
from apps.participants.models import ParticipantToken

from .models import AnswerOption, AnswerResponse, Question, QuestionnaireVersion, ScoringResult, TestBundle


@pytest.mark.django_db
def test_question_order_is_unique_within_questionnaire_version():
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1")
    Question.objects.create(questionnaire_version=qv, order=1, code="mobility", text="…", indicator_code="eq5d_mobility")
    with pytest.raises(IntegrityError):
        Question.objects.create(questionnaire_version=qv, order=1, code="self_care", text="…", indicator_code="eq5d_self_care")


@pytest.mark.django_db
def test_answer_response_is_idempotent_per_token_stage_question():
    # ТЗ FR-06.6: повторная отправка ответа не должна создавать дубли.
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1")
    question = Question.objects.create(questionnaire_version=qv, order=1, code="mobility", text="…", indicator_code="eq5d_mobility")
    option = AnswerOption.objects.create(question=question, order=1, value=1, label="Нет проблем")

    AnswerResponse.objects.update_or_create(
        token=token, stage="baseline", question=question, defaults={"selected_option": option}
    )
    AnswerResponse.objects.update_or_create(
        token=token, stage="baseline", question=question, defaults={"selected_option": option}
    )

    assert AnswerResponse.objects.filter(token=token, stage="baseline", question=question).count() == 1


@pytest.mark.django_db
def test_scoring_result_is_unique_per_token_stage_indicator():
    org = Organization.objects.create(name="ООО Ромашка")
    token = ParticipantToken.objects.create(organization=org)
    bundle = TestBundle.objects.create(code="test-bundle", name="Тестовый комплект")
    ScoringResult.objects.create(token=token, bundle=bundle, stage="baseline", indicator_code="hads_anxiety", raw_score=14)
    with pytest.raises(IntegrityError):
        ScoringResult.objects.create(token=token, bundle=bundle, stage="baseline", indicator_code="hads_anxiety", raw_score=10)
