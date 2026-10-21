"""Тесты scoring-движка (ТЗ FR-07): суммирование, идемпотентность, направление шкал, зоны.

Границы зон HADS и Спилбергера–Ханина — реальные, из методички методолога ("4 теста для бота,
с вопросами и легендой — Vizion оценка состояния"); EQ-5D VAS таких границ в методичке не имеет и
по-прежнему классифицируется черновой ratio-логикой (доля от максимума шкалы)."""
from decimal import Decimal

import pytest

from apps.organizations.models import Organization
from apps.participants.models import ParticipantToken

from . import scoring
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


def test_zone_for_high_is_bad_indicator_falls_back_to_ratio_without_fixed_boundaries(monkeypatch):
    # "hads_anxiety"/"situational_anxiety" и т.п. теперь классифицируются реальными границами
    # (см. тесты ниже) — ratio-фолбэк по-прежнему используется для показателей без них (EQ-5D
    # профильные измерения). Синтетический код гарантированно отсутствует в ZONE_BOUNDARIES/FIXED_MAX.
    monkeypatch.setitem(scoring.INDICATOR_DIRECTION, "_test_bad_indicator", "high_is_bad")
    monkeypatch.setattr(scoring, "max_possible_score", lambda code: 4)
    assert zone_for("_test_bad_indicator", 1) == "низкая"
    assert zone_for("_test_bad_indicator", 4) == "выраженная"


def test_zone_for_high_is_good_indicator_is_inverted(monkeypatch):
    monkeypatch.setitem(scoring.INDICATOR_DIRECTION, "_test_good_indicator", "high_is_good")
    monkeypatch.setattr(scoring, "max_possible_score", lambda code: 4)
    # high_is_good (вроде самооценки здоровья): низкий балл — плохо, высокий — хорошо.
    assert zone_for("_test_good_indicator", 1) == "низкая"
    assert zone_for("_test_good_indicator", 4) == "отличная"


@pytest.mark.django_db
def test_trend_for_accounts_for_scale_direction():
    # Для «high_is_bad» рост балла — ухудшение; для «high_is_good» — наоборот.
    assert trend_for("hads_anxiety", before=Decimal(2), after=Decimal(4)) == "worsened"
    assert trend_for("hads_anxiety", before=Decimal(4), after=Decimal(2)) == "improved"
    assert trend_for("eq5d_vas", before=Decimal(2), after=Decimal(4)) == "improved"
    assert trend_for("eq5d_vas", before=Decimal(4), after=Decimal(2)) == "worsened"
    assert trend_for("hads_anxiety", before=Decimal(3), after=Decimal(3)) == "stable"


@pytest.mark.parametrize(
    "score,expected",
    [(0, "норма"), (7, "норма"), (8, "субклинически выраженная тревога"), (10, "субклинически выраженная тревога"),
     (11, "клинически выраженная тревога"), (21, "клинически выраженная тревога")],
)
def test_hads_anxiety_zone_boundaries_match_the_methodology(score, expected):
    assert zone_for("hads_anxiety", score) == expected


@pytest.mark.parametrize(
    "score,expected",
    [(30, "низкая"), (31, "умеренная"), (44, "умеренная"), (45, "высокая"), (80, "высокая")],
)
def test_stai_zone_boundaries_match_the_methodology(score, expected):
    assert zone_for("situational_anxiety", score) == expected
    assert zone_for("trait_anxiety", score) == expected


@pytest.mark.django_db
def test_eq5d_vas_free_numeric_answer_is_scored_without_an_option(token):
    # EQ-5D VAS — единственный вопрос без вариантов ответа: балл = сам числовой ввод (ТЗ FR-06/FR-07).
    # Границ зон в методичке для него нет (это не клиническая шкала с cut-off'ами) — классификация
    # по-прежнему ratio-фолбэк, но с фиксированным максимумом 100 (apps/assessments/scoring.py::FIXED_MAX),
    # а не из несуществующих вариантов ответа.
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_EQ5D, version_label="v1", is_active=True)
    question = Question.objects.create(questionnaire_version=qv, order=1, code="vas", text="…", indicator_code="eq5d_vas")
    assert question.options.count() == 0

    AnswerResponse.objects.create(token=token, stage="baseline", question=question, selected_option=None, raw_value="72")

    results = compute_scores_for_stage(token, "baseline")

    assert len(results) == 1
    assert results[0].indicator_code == "eq5d_vas"
    assert results[0].raw_score == Decimal(72)
    assert results[0].interpretation_zone == "хорошая"


@pytest.mark.django_db
def test_hads_items_use_their_own_per_question_key_not_a_uniform_direction(token):
    # Реверсивные пункты HADS: ключ зависит от конкретной формулировки вопроса, а не от
    # чёт/нечет номера — см. комментарий в seed_real_questionnaires.py. Берём 2 реальных пункта
    # с противоположным направлением ключа у одного и того же "тревожного" текста ответа.
    qv = QuestionnaireVersion.objects.create(code=QuestionnaireVersion.CODE_HADS, version_label="v1", is_active=True)

    q1 = Question.objects.create(questionnaire_version=qv, order=1, code="hads_1", text="…", indicator_code="hads_anxiety")
    AnswerOption.objects.create(question=q1, order=1, value=3, label="Всё время")
    AnswerOption.objects.create(question=q1, order=4, value=0, label="Совсем не испытываю")

    q7 = Question.objects.create(questionnaire_version=qv, order=7, code="hads_7", text="…", indicator_code="hads_anxiety")
    AnswerOption.objects.create(question=q7, order=1, value=0, label="Определенно, это так")
    AnswerOption.objects.create(question=q7, order=4, value=3, label="Совсем не могу")

    AnswerResponse.objects.create(
        token=token, stage="baseline", question=q1, selected_option=q1.options.get(label="Всё время")
    )
    AnswerResponse.objects.create(
        token=token, stage="baseline", question=q7, selected_option=q7.options.get(label="Совсем не могу")
    )

    results = compute_scores_for_stage(token, "baseline")

    assert len(results) == 1
    assert results[0].indicator_code == "hads_anxiety"
    assert results[0].raw_score == Decimal(6)  # 3 (Q1 "Всё время") + 3 (Q7 "Совсем не могу")


@pytest.mark.django_db
def test_scoring_records_the_questionnaire_version_that_produced_the_score(token, anxiety_question):
    # Положение о ролях, п. 5.2: балл должен быть привязан к версии методики, которой он посчитан,
    # иначе шкалы разных версий неотличимы в агрегате.
    question, options = anxiety_question
    AnswerResponse.objects.create(token=token, stage="baseline", question=question, selected_option=options[1])

    result = compute_scores_for_stage(token, "baseline")[0]

    assert result.questionnaire_version_id == question.questionnaire_version_id


@pytest.mark.django_db
def test_mixed_version_answers_are_skipped_instead_of_scored_under_one_version(token, anxiety_question):
    """Ответы одного показателя из двух версий — смешанная шкала, балл не сохраняется.

    Так выглядят исторические данные, когда одновременно были активны опросник-заглушка и реальная
    методика. Приписать такую сумму одной из версий нельзя, поэтому записи не появляется вовсе —
    и при этом не падает сохранение ответа участником (scoring вызывается внутри submit_answer).
    """
    question, options = anxiety_question
    other_version = QuestionnaireVersion.objects.create(
        code=QuestionnaireVersion.CODE_HADS, version_label="dummy-v0", is_active=False
    )
    stale_question = Question.objects.create(
        questionnaire_version=other_version, order=1, code="anxiety_old", text="…", indicator_code="hads_anxiety"
    )
    stale_option = AnswerOption.objects.create(question=stale_question, order=1, value=2, label="2")

    AnswerResponse.objects.create(token=token, stage="baseline", question=question, selected_option=options[1])
    AnswerResponse.objects.create(token=token, stage="baseline", question=stale_question, selected_option=stale_option)

    results = compute_scores_for_stage(token, "baseline")

    assert results == []
    assert not ScoringResult.objects.filter(token=token, stage="baseline", indicator_code="hads_anxiety").exists()
