"""Контрольный пример Excel, пороги и полный маршрут новой методологии."""
from datetime import timedelta
from io import BytesIO
import csv
import io
import json

import pytest
from django.core.management import call_command
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.assessments.iipb import ANCHORS, METHODOLOGY, RANGES, InvalidIIPBInput, calculate_iipb, compare_iipb, normalize
from apps.assessments.iipb_services import save_iipb_result
from apps.assessments.models import AnswerOption, AnswerResponse, IIPBResult, Question, QuestionnaireVersion, ScoringResult, TestBundle, TestBundleItem
from apps.organizations.models import Organization, Stream
from apps.participants.models import ParticipantToken
from apps.participants import services
from apps.reporting.export_services import build_csv, build_pdf, build_xlsx
from apps.reporting.services import ReportNotReady, build_personal_report

BEFORE = dict(zip(RANGES, [9, 6, 46, 48, 1, 1, 2, 2, 3, 60]))
AFTER = dict(zip(RANGES, [6, 4, 35, 47, 1, 1, 1, 2, 2, 75]))
BEST = {key: (maximum if key == "eq5d_vas" else minimum) for key, (minimum, maximum) in RANGES.items()}
WORST = {key: (minimum if key == "eq5d_vas" else maximum) for key, (minimum, maximum) in RANGES.items()}


def test_excel_control_example():
    before, after = calculate_iipb(BEFORE), calculate_iipb(AFTER)
    assert (before["index"], before["level"], after["index"], after["level"]) == (66, "II", 79, "I")
    assert before["domains"]["anxiety"] == pytest.approx(52.7777777777778)
    assert before["domains"]["health"] == pytest.approx(67.5387596899225)
    assert before["red_flags"] == []
    assert [flag["code"] for flag in before["yellow_flags"]] == ["Y1"]
    assert not after["yellow_flags"]
    change = compare_iipb(before, after)
    assert (change["delta_pp"], change["delta_percent"], change["level_change"]) == (13, 19.7, "II → I")


@pytest.mark.parametrize("code", ANCHORS)
def test_normalization_at_every_anchor_and_outside(code):
    anchors = ANCHORS[code]
    for value, expected in anchors:
        assert normalize(value, anchors) == expected
    assert normalize(-100, anchors) == anchors[0][1]
    assert normalize(1000, anchors) == anchors[-1][1]


def test_endpoints_and_zero_baseline_relative_change():
    best, worst = calculate_iipb(BEST), calculate_iipb(WORST)
    assert (best["index"], best["level"]) == (100, "I")
    assert (worst["index"], worst["level"]) == (0, "IV")
    assert compare_iipb(worst, best)["delta_percent"] is None


@pytest.mark.parametrize("key", RANGES)
@pytest.mark.parametrize("value", [None, "", "NaN", "Infinity", True, 0.5, -1, 101])
def test_invalid_or_fractional_data_never_produce_an_index(key, value):
    with pytest.raises(InvalidIIPBInput):
        calculate_iipb({**BEFORE, key: value})


@pytest.mark.parametrize("key", RANGES)
def test_all_ten_values_including_trait_are_required(key):
    values = BEFORE.copy()
    values.pop(key)
    with pytest.raises(InvalidIIPBInput):
        calculate_iipb(values)


def test_trait_changes_only_background_marker():
    before, after = calculate_iipb({**BEST, "trait_anxiety": 30}), calculate_iipb({**BEST, "trait_anxiety": 45})
    assert before["index"] == after["index"] == 100
    assert before["trait_marker"]["label"] == "низкая"
    assert after["trait_marker"]["label"] == "высокая"


@pytest.mark.parametrize("key,value,flag", [
    ("hads_anxiety", 11, "R1"), ("hads_depression", 11, "R2"), ("eq5d_anxiety_depression", 4, "R3"),
])
def test_red_flags_override_a_good_index(key, value, flag):
    result = calculate_iipb({**BEST, key: value})
    assert result["index"] >= 75
    assert result["conclusion"] == "Требуется консультация специалиста"
    assert [f["code"] for f in result["red_flags"]] == [flag]


@pytest.mark.parametrize("key,value,flag", [("situational_anxiety", 45, "Y1"), ("eq5d_vas", 39, "Y2"), ("eq5d_pain", 4, "Y3")])
def test_yellow_flags_preserve_level_conclusion(key, value, flag):
    result = calculate_iipb({**BEST, key: value})
    assert result["conclusion"] == result["level_label"]
    assert [f["code"] for f in result["yellow_flags"]] == [flag]
    assert flag not in [f["code"] for f in calculate_iipb({**BEST, key: value - 1 if key != "eq5d_vas" else 40})["yellow_flags"]]


def test_arithmetic_half_rounds_up_after_six_decimals():
    # Точное среднее = 57.5: A=78.75, D=58.333..., H=35.416... (§4.4).
    values = {**BEST, "hads_anxiety": 7, "situational_anxiety": 27, "hads_depression": 9,
              "eq5d_mobility": 4, "eq5d_self_care": 2, "eq5d_daily_activities": 2,
              "eq5d_pain": 2, "eq5d_anxiety_depression": 2, "eq5d_vas": 22}
    assert calculate_iipb(values)["index"] == 58


def test_persistent_flags_and_worsening_level_require_routing():
    before = calculate_iipb({**BEFORE, "eq5d_vas": 39})
    after = calculate_iipb({**BEFORE, "hads_depression": 21, "eq5d_vas": 20})
    change = compare_iipb(before, after)
    assert change["trend"] == "worsened"
    assert len(change["actions"]) == 4
    with pytest.raises(ValueError):
        compare_iipb(before, {**after, "version": "0.2"})


@pytest.fixture
def configured(db):
    org = Organization.objects.create(name="ИИПБ тест", specialist_contact="Координатор: кабинет 1")
    stream = Stream.objects.create(organization=org, name="ИИПБ", min_group_size=2)
    call_command("seed_iipb_methodology", stdout=io.StringIO())
    bundle = TestBundle.objects.get(code=METHODOLOGY)
    token = ParticipantToken.objects.create(organization=org, stream=stream)
    for consent_type in ("informed_notice", "data_processing"):
        services.record_consent(token, consent_type, METHODOLOGY, True)
    return org, stream, bundle, token


def complete_stage(token, bundle, values, *, stage):
    remaining = {code: values[code] for code in RANGES}
    questions = services.active_questions(bundle)
    counts = {code: sum(q.indicator_code == code for q in questions) for code in RANGES}
    for question in questions:
        code = question.indicator_code
        if question.options.exists():
            minimum, maximum = (1, 4) if code.endswith("anxiety") and not code.startswith("hads") else (0, 3) if code.startswith("hads") else (1, 5)
            value = min(maximum, remaining[code] - (counts[code] - 1) * minimum)
            option = question.options.get(value=value)
            state = services.submit_answer(token, question.id, option.id, "", bundle, stage=stage)
        else:
            value = remaining[code]
            state = services.submit_answer(token, question.id, None, str(value), bundle, stage=stage)
        remaining[code] -= value
        counts[code] -= 1
    return state


def test_seed_preserves_legacy_and_uses_5l_and_seven_trait_reverse_items(configured):
    _, _, bundle, _ = configured
    versions = [item.questionnaire_version for item in bundle.items.all()]
    assert [v.code for v in versions] == ["hads", "stai", "eq5d"]
    assert len(services.active_questions(bundle)) == 60
    assert all(q.options.count() == 5 for q in versions[2].questions.exclude(indicator_code="eq5d_vas"))
    for code, expected in (("situational_anxiety", 10), ("trait_anxiety", 7)):
        assert sum(q.options.get(order=1).value == 4 for q in versions[1].questions.filter(indicator_code=code)) == expected
    call_command("seed_iipb_methodology", stdout=io.StringIO())
    assert TestBundle.objects.filter(methodology=METHODOLOGY).count() == 1


def test_two_measurements_report_immutable_history_and_seven_day_gate(configured, monkeypatch):
    _, _, bundle, token = configured
    with pytest.raises(ReportNotReady):
        build_personal_report(token, bundle)
    state = complete_stage(token, bundle, BEFORE, stage="baseline")
    assert state["stage"] == "followup" and state["followup_locked"]
    assert state["questions"] == []
    assert state["baseline_result"]["index"] == 66
    report = build_personal_report(token, bundle)
    assert report["status"] == "baseline_only" and report["iipb"]["dynamics"] is None
    baseline = IIPBResult.objects.get(token=token)
    first = services.active_questions(bundle)[0]
    with pytest.raises(services.FollowupTooEarly):
        services.submit_answer(token, first.id, first.options.first().id, "", bundle, stage="followup")
    monkeypatch.setattr(timezone, "now", lambda: baseline.measured_at + timedelta(days=7) - timedelta(seconds=1))
    assert services.session_state(token, bundle)["followup_locked"]
    monkeypatch.setattr(timezone, "now", lambda: baseline.measured_at + timedelta(days=7))
    assert not services.session_state(token, bundle)["followup_locked"]
    assert complete_stage(token, bundle, AFTER, stage="followup")["stage"] is None
    report = build_personal_report(token, bundle)
    assert report["iipb"]["dynamics"]["delta_pp"] == 13
    assert "trait_anxiety" not in [card["indicator_code"] for card in report["cards"]]
    original = baseline.payload.copy()
    ScoringResult.objects.filter(token=token, bundle=bundle, stage="baseline").update(raw_score=0)
    save_iipb_result(token, "baseline", bundle)
    assert IIPBResult.objects.get(pk=baseline.pk).payload == original
    assert build_personal_report(token, bundle)["iipb"]["baseline"]["index"] == 66
    call_command("recompute_scores", stdout=io.StringIO())
    assert IIPBResult.objects.get(pk=baseline.pk).payload == original


def test_api_enforces_order_bundle_and_consent_and_blocks_early_followup(configured):
    _, _, bundle, token = configured
    client = APIClient()
    question = services.active_questions(bundle)[-2]
    payload = {"bundle_id": bundle.pk, "stage": "baseline", "question_id": question.pk, "option_id": question.options.first().pk}
    url = f"/api/participant/sessions/{token.token}/answers/"
    assert client.post(url, payload, format="json").status_code == 409
    assert client.post(url, {**payload, "bundle_id": None}, format="json").status_code == 404
    complete_stage(token, bundle, BEFORE, stage="baseline")
    assert client.post(url, {**payload, "stage": "followup"}, format="json").status_code == 409
    response = client.get(f"/api/participant/reports/{token.token}/?bundle_id={bundle.pk}")
    assert response.status_code == 200 and response.data["iipb"]["baseline"]["index"] == 66
    services.record_consent(token, "data_processing", METHODOLOGY, False)
    assert client.get(f"/api/participant/reports/{token.token}/?bundle_id={bundle.pk}").status_code == 403


def test_old_consent_requires_new_informed_notice(configured):
    _, _, bundle, token = configured
    token.consents.all().delete()
    services.record_consent(token, "data_processing", "v1", True)
    assert services.session_state(token, bundle)["consent_status"] == "required"


def test_retired_legacy_bundle_remains_available_only_to_its_existing_participant(configured):
    org, _, _, token = configured
    legacy = TestBundle.objects.create(code="prodex-v1", name="Старый EQ-5D-3L", is_active=False)
    version = QuestionnaireVersion.objects.create(code="eq5d", version_label="legacy-3l", is_active=False)
    TestBundleItem.objects.create(bundle=legacy, questionnaire_version=version, order=1)
    question = Question.objects.create(questionnaire_version=version, order=1, code="mobility", indicator_code="eq5d_mobility", text="Подвижность")
    option = AnswerOption.objects.create(question=question, order=1, label="Без трудностей", value=1)
    AnswerResponse.objects.create(token=token, bundle=legacy, stage="baseline", question=question, selected_option=option)
    assert services.get_bundle_for_token(token, legacy.pk) == legacy
    assert services.active_questions(legacy) == [question]
    assert legacy.pk in [b["id"] for b in services.participant_home_state(token)["bundles"]]
    new_token = ParticipantToken.objects.create(organization=org)
    with pytest.raises(services.BundleUnavailable):
        services.get_bundle_for_token(new_token, legacy.pk)
    call_command("recompute_scores", stdout=io.StringIO())
    assert ScoringResult.objects.get(token=token, bundle=legacy).raw_score == 1
    assert not IIPBResult.objects.filter(bundle=legacy).exists()


def test_aggregate_and_exports_use_minimum_five_and_pair_threshold(configured):
    org, stream, bundle, token = configured
    for stage, values in (("baseline", BEFORE), ("followup", AFTER)):
        payload = calculate_iipb(values)
        IIPBResult.objects.create(token=token, bundle=bundle, stage=stage, version="0.1", version_date="2026-11-16",
                                  index=payload["index"], level=payload["level"], payload=payload, measured_at=timezone.now())
    tokens = ParticipantToken.objects.filter(organization=org)
    from apps.reporting.iipb_services import iipb_overview
    suppressed = iipb_overview(tokens, bundle, 2)
    assert suppressed["baseline"] == {"participant_count": 1, "is_suppressed": True}
    for _ in range(4):
        extra = ParticipantToken.objects.create(organization=org, stream=stream)
        for result in token.iipb_results.all():
            IIPBResult.objects.create(token=extra, bundle=bundle, stage=result.stage, version=result.version,
                                      version_date=result.version_date, index=result.index, level=result.level,
                                      payload=result.payload, measured_at=result.measured_at)
    data = iipb_overview(tokens, bundle, 2)
    assert data["baseline"]["mean"] == data["baseline"]["median"] == 66
    assert data["baseline"]["yellow_flag_count"] == 5
    assert data["trend"]["mean_delta"] == data["trend"]["median_delta"] == 13
    overview = {"organization": {"id": org.pk, "name": org.name}, "stream": None,
                "coverage": {"participants": 5}, "completion": {"baseline_completed": 5, "followup_completed": 5},
                "indicators": [], "iipb": data}
    assert token.token not in json.dumps(data)
    wb = load_workbook(BytesIO(build_xlsx(overview)))
    assert "ИИПБ v0.1" in wb.sheetnames
    assert wb["ИИПБ v0.1"]["B28"].value == 13
    csv_rows = list(csv.reader(io.StringIO(build_csv(overview).decode("utf-8-sig")), delimiter=";"))
    assert len(csv_rows[0]) == len(csv_rows[1])
    assert csv_rows[1][csv_rows[0].index("До курса: Медиана ИИПБ, %")] == "66"
    assert build_pdf(overview).startswith(b"%PDF")
    IIPBResult.objects.filter(token=token, stage="followup").delete()
    partial = iipb_overview(tokens, bundle, 5)
    assert partial["trend"] == {"paired_count": 4, "is_suppressed": True}
    partial_overview = {**overview, "iipb": partial}
    wb = load_workbook(BytesIO(build_xlsx(partial_overview)))
    assert wb["ИИПБ v0.1"]["C6"].value is None
    assert wb["ИИПБ v0.1"]["B28"].value is None
    csv_rows = list(csv.reader(io.StringIO(build_csv(partial_overview).decode("utf-8-sig")), delimiter=";"))
    assert csv_rows[1][csv_rows[0].index("Средняя Δ ИИПБ, п.п.")] == ""
