"""Тесты сборки персонального отчёта (ТЗ FR-08)."""
import pytest

from apps.assessments.models import ScoringResult
from apps.assessments.scoring import REPORT_INDICATORS
from apps.organizations.models import Organization
from apps.participants.models import ParticipantToken

from .services import ReportNotReady, build_personal_report


@pytest.fixture
def token(db):
    organization = Organization.objects.create(name="ООО Ромашка")
    return ParticipantToken.objects.create(organization=organization)


def _score(token, stage, indicator_code, raw_score, zone="умеренная"):
    ScoringResult.objects.create(token=token, stage=stage, indicator_code=indicator_code, raw_score=raw_score, interpretation_zone=zone)


@pytest.mark.django_db
def test_report_is_not_ready_until_both_stages_are_fully_scored(token):
    for code in REPORT_INDICATORS:
        _score(token, "baseline", code, 2)
    # followup ещё не посчитан ни по одному показателю
    with pytest.raises(ReportNotReady):
        build_personal_report(token)


@pytest.mark.django_db
def test_legacy_report_contains_only_indicators_present_in_both_stages(token):
    for code in REPORT_INDICATORS:
        _score(token, "baseline", code, 2)
        _score(token, "followup", code, 2)
    ScoringResult.objects.filter(token=token, stage="followup", indicator_code=REPORT_INDICATORS[0]).delete()

    report = build_personal_report(token)
    assert {card["indicator_code"] for card in report["cards"]} == set(REPORT_INDICATORS[1:])


@pytest.mark.django_db
def test_report_contains_exactly_five_cards_with_before_after_change_and_trend(token):
    # ТЗ FR-08.1/FR-08.2: ровно 5 карточек, у каждой — было/стало/изменение/интерпретация.
    for code in REPORT_INDICATORS:
        _score(token, "baseline", code, 3)
        _score(token, "followup", code, 1)  # для всех high_is_bad-показателей это улучшение

    report = build_personal_report(token)

    assert len(report["cards"]) == 5
    assert {card["indicator_code"] for card in report["cards"]} == set(REPORT_INDICATORS)
    for card in report["cards"]:
        assert card["before"]["raw_score"] == 3
        assert card["after"]["raw_score"] == 1
        assert card["change"] == -2
        assert "trend" in card


@pytest.mark.django_db
def test_report_does_not_combine_indicators_into_a_single_index(token):
    # PROJECT_RULES №2: ни одного суммарного/усреднённого числа по всем показателям сразу.
    for code in REPORT_INDICATORS:
        _score(token, "baseline", code, 2)
        _score(token, "followup", code, 2)

    report = build_personal_report(token)

    forbidden_keys = {"index", "overall_score", "total_score", "combined_score"}
    assert forbidden_keys.isdisjoint(report.keys())


@pytest.mark.django_db
def test_report_summary_reflects_mixed_dynamics(token):
    # hads_anxiety улучшился (3→1), eq5d_vas ухудшился (у high_is_good: 80→60 — хуже), остальные без изменений.
    _score(token, "baseline", "hads_anxiety", 3)
    _score(token, "followup", "hads_anxiety", 1)
    _score(token, "baseline", "eq5d_vas", 80)
    _score(token, "followup", "eq5d_vas", 60)
    for code in ("situational_anxiety", "trait_anxiety", "hads_depression"):
        _score(token, "baseline", code, 2)
        _score(token, "followup", code, 2)

    report = build_personal_report(token)

    trends = {card["indicator_code"]: card["trend"] for card in report["cards"]}
    assert trends["hads_anxiety"] == "improved"
    assert trends["eq5d_vas"] == "worsened"
    assert "разнонаправленн" in report["summary"].lower()


@pytest.mark.django_db
def test_report_is_cached_on_the_token(token):
    # Кэш — поля report_payload/report_generated_at на самом токене (бывшая отдельная таблица
    # PersonalReportSnapshot), поэтому "не плодить снимки" гарантировано структурой, а не constraint'ом.
    for code in REPORT_INDICATORS:
        _score(token, "baseline", code, 2)
        _score(token, "followup", code, 2)

    assert token.report_payload is None

    payload = build_personal_report(token)
    token.refresh_from_db()
    assert token.report_payload == payload
    assert token.report_generated_at is not None

    first_generated_at = token.report_generated_at
    build_personal_report(token)  # повторный вызов обновляет тот же кэш, а не создаёт новую запись
    token.refresh_from_db()
    assert token.report_generated_at >= first_generated_at
