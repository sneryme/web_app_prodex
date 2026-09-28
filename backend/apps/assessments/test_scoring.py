"""Тесты scoring-движка (ТЗ FR-07): baseline/followup баллы, зоны, направление шкал."""
from decimal import Decimal

import pytest

from apps.organizations.models import Organization
from apps.participants.models import ParticipantToken

from .models import AnswerOption, AnswerResponse, Question, QuestionnaireVersion, ScoringResult
from .scoring import compute_scores_for_stage, trend_for, zone_for


@pytest.fixture
def token(db):
    organization = Organization.objects.create(name="ООО Ромашка")
    return ParticipantToken.objects.create(organization=organization)


@pytest.fixture
def anxiety_question(db):
    version = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)
    question = Question.objects.create(
        questionnaire_version=version, order=1, code="anxiety_1", text="…", indicator_code="hads_anxiety"
    )
    options = [
        AnswerOption.objects.create(question=question, order=i, value=i, label=str(i)) for i in range(1, 5)
    ]
    return question, options


@pytest.mark.django_db
def test_compute_scores_sums_answered_options_per_indicator(token, anxiety_question):
    question, options = anxiety_question
    AnswerResponse.objects.create(token=token, stage="baseline", question=question, selected_option=options[2])  # value=3

    results = compute_scores_for_stage(token, "baseline")

    assert len(results) == 1
    result = ScoringResult.objects.get(token=token, stage="baseline", indicator_code="hads_anxiety")
    assert result.raw_score == Decimal(3)


@pytest.mark.django_db
def test_compute_scores_is_idempotent_and_updates_in_place(token, anxiety_question):
    question, options = anxiety_question
    AnswerResponse.objects.create(token=token, stage="baseline", question=question, selected_option=options[0])
    compute_scores_for_stage(token, "baseline")

    # Участник меняет ответ до пересчёта — повторный вызов должен обновить, а не задвоить строку.
    AnswerResponse.objects.filter(token=token, stage="baseline", question=question).update(selected_option=options[3])
    compute_scores_for_stage(token, "baseline")

    assert ScoringResult.objects.filter(token=token, stage="baseline", indicator_code="hads_anxiety").count() == 1
    result = ScoringResult.objects.get(token=token, stage="baseline", indicator_code="hads_anxiety")
    assert result.raw_score == Decimal(4)


@pytest.mark.django_db
def test_zone_for_high_is_bad_indicator_grows_with_score(anxiety_question):
    # HADS (high_is_bad): максимум по единственному вопросу — 4, значит зона зависит от доли raw_score/4.
    assert zone_for("hads_anxiety", 1) == "низкая"
    assert zone_for("hads_anxiety", 4) == "выраженная"


@pytest.mark.django_db
def test_zone_for_high_is_good_indicator_is_inverted(db):
    version = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=True)
    question = Question.objects.create(
        questionnaire_version=version, order=1, code="vas", text="…", indicator_code="eq5d_vas"
    )
    AnswerOption.objects.create(question=question, order=1, value=1, label="1")
    AnswerOption.objects.create(question=question, order=2, value=4, label="4")

    # EQ-5D VAS (high_is_good): низкий балл — плохо, высокий — хорошо (обратная логика к HADS).
    assert zone_for("eq5d_vas", 1) == "низкая"
    assert zone_for("eq5d_vas", 4) == "отличная"


@pytest.mark.django_db
def test_trend_for_accounts_for_scale_direction():
    # Для «high_is_bad» рост балла — ухудшение; для «high_is_good» — наоборот.
    assert trend_for("hads_anxiety", before=Decimal(2), after=Decimal(4)) == "worsened"
    assert trend_for("hads_anxiety", before=Decimal(4), after=Decimal(2)) == "improved"
    assert trend_for("eq5d_vas", before=Decimal(2), after=Decimal(4)) == "improved"
    assert trend_for("eq5d_vas", before=Decimal(4), after=Decimal(2)) == "worsened"
    assert trend_for("hads_anxiety", before=Decimal(3), after=Decimal(3)) == "stable"
