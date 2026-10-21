"""Тесты группового дашборда работодателя (ТЗ FR-09)."""
import pytest

from apps.assessments.models import QuestionnaireVersion, ScoringResult
from apps.assessments.scoring import REPORT_INDICATORS
from apps.organizations.models import Organization, Stream
from apps.participants.models import ParticipantToken

from .employer_services import list_streams, organization_overview


def _token(org, stream=None, baseline_status="not_started", followup_status="not_started"):
    return ParticipantToken.objects.create(
        organization=org, stream=stream, baseline_status=baseline_status, followup_status=followup_status
    )


def _score(token, stage, indicator_code, raw_score, zone="умеренная", version=None):
    # Версия обязательна по смыслу: агрегат берёт только баллы действующей версии методики,
    # иначе в одной группе по indicator_code смешиваются несопоставимые шкалы.
    ScoringResult.objects.create(
        token=token,
        stage=stage,
        indicator_code=indicator_code,
        raw_score=raw_score,
        interpretation_zone=zone,
        questionnaire_version=version or _active_version(),
    )


def _active_version():
    version, _ = QuestionnaireVersion.objects.get_or_create(
        code=QuestionnaireVersion.CODE_HADS, version_label="test-active", defaults={"is_active": True}
    )
    return version


@pytest.fixture
def org(db):
    return Organization.objects.create(name="ООО Ромашка")


@pytest.mark.django_db
def test_coverage_and_completion_counts(org):
    _token(org, baseline_status="completed", followup_status="completed")
    _token(org, baseline_status="completed", followup_status="not_started")
    _token(org, baseline_status="not_started", followup_status="not_started")

    overview = organization_overview(org)

    assert overview["coverage"]["participants"] == 3
    assert overview["completion"]["baseline_completed"] == 2
    assert overview["completion"]["followup_completed"] == 1


@pytest.mark.django_db
def test_overview_has_exactly_five_indicators_matching_the_personal_report(org):
    overview = organization_overview(org)
    assert {i["indicator_code"] for i in overview["indicators"]} == set(REPORT_INDICATORS)
    assert len(overview["indicators"]) == 5


@pytest.mark.django_db
def test_small_group_is_suppressed_below_the_stream_threshold(org):
    # min_group_size=3: 2 участника с результатом — меньше порога, группа скрыта (ТЗ FR-09.4).
    stream = Stream.objects.create(organization=org, code="small", min_group_size=3)
    for _ in range(2):
        t = _token(org, stream=stream)
        _score(t, "baseline", "hads_anxiety", 10)

    overview = organization_overview(org, stream=stream)
    hads = next(i for i in overview["indicators"] if i["indicator_code"] == "hads_anxiety")

    assert hads["baseline"]["is_suppressed"] is True
    assert hads["baseline"]["participant_count"] == 2
    assert "mean" not in hads["baseline"]
    assert "zone_distribution" not in hads["baseline"]


@pytest.mark.django_db
def test_group_at_or_above_threshold_shows_mean_and_distribution(org):
    stream = Stream.objects.create(organization=org, code="big", min_group_size=3)
    for score, zone in [(5, "норма"), (9, "субклинически выраженная тревога"), (12, "клинически выраженная тревога")]:
        t = _token(org, stream=stream)
        _score(t, "baseline", "hads_anxiety", score, zone=zone)

    overview = organization_overview(org, stream=stream)
    hads = next(i for i in overview["indicators"] if i["indicator_code"] == "hads_anxiety")

    assert hads["baseline"]["is_suppressed"] is False
    assert hads["baseline"]["participant_count"] == 3
    assert hads["baseline"]["mean"] == round((5 + 9 + 12) / 3, 2)  # сервис округляет среднее до сотых
    assert hads["baseline"]["zone_distribution"] == {
        "норма": 1,
        "субклинически выраженная тревога": 1,
        "клинически выраженная тревога": 1,
    }


@pytest.mark.django_db
def test_trend_block_counts_improved_and_worsened_among_paired_participants(org):
    stream = Stream.objects.create(organization=org, code="trend", min_group_size=2)
    # hads_anxiety: high_is_bad — рост балла = ухудшение.
    for before, after in [(5, 12), (5, 12), (12, 5)]:
        t = _token(org, stream=stream)
        _score(t, "baseline", "hads_anxiety", before)
        _score(t, "followup", "hads_anxiety", after)

    overview = organization_overview(org, stream=stream)
    hads = next(i for i in overview["indicators"] if i["indicator_code"] == "hads_anxiety")

    assert hads["trend"]["is_suppressed"] is False
    assert hads["trend"]["paired_count"] == 3
    assert hads["trend"]["worsened"] == 2
    assert hads["trend"]["improved"] == 1


@pytest.mark.django_db
def test_stream_filter_changes_the_returned_data(org):
    stream_a = Stream.objects.create(organization=org, code="a", min_group_size=1)
    stream_b = Stream.objects.create(organization=org, code="b", min_group_size=1)
    t_a = _token(org, stream=stream_a)
    _score(t_a, "baseline", "hads_anxiety", 3)
    t_b = _token(org, stream=stream_b)
    _score(t_b, "baseline", "hads_anxiety", 18)

    overview_a = organization_overview(org, stream=stream_a)
    overview_b = organization_overview(org, stream=stream_b)

    mean_a = next(i for i in overview_a["indicators"] if i["indicator_code"] == "hads_anxiety")["baseline"]["mean"]
    mean_b = next(i for i in overview_b["indicators"] if i["indicator_code"] == "hads_anxiety")["baseline"]["mean"]
    assert mean_a != mean_b
    assert overview_a["coverage"]["participants"] == 1
    assert overview_b["coverage"]["participants"] == 1


@pytest.mark.django_db
def test_overview_payload_never_contains_tokens_or_individual_answers(org):
    # ТЗ FR-09.5: ни строк участников, ни токенов, ни отдельных ответов в ответе API.
    stream = Stream.objects.create(organization=org, code="leak-check", min_group_size=1)
    t = _token(org, stream=stream, baseline_status="completed")
    _score(t, "baseline", "hads_anxiety", 7)

    overview = organization_overview(org, stream=stream)

    serialized = str(overview)
    assert t.token not in serialized
    assert "token" not in overview["indicators"][0]["baseline"]
    assert "selected_option" not in serialized and "raw_value" not in serialized


@pytest.mark.django_db
def test_scores_from_a_retired_questionnaire_version_are_excluded(org):
    """Положение о ролях, п. 5.2: новая версия не подменяет исторические результаты.

    Баллы снятой с публикации версии не должны попадать в агрегат: шкалы несопоставимы, и среднее
    по их смеси бессмысленно. Проверяем именно через среднее, а не через флаг, — подмешанный балл
    обязан не влиять на цифру.
    """
    retired = QuestionnaireVersion.objects.create(
        code=QuestionnaireVersion.CODE_HADS, version_label="dummy-v0", is_active=False
    )
    stream = Stream.objects.create(organization=org, code="versions", min_group_size=1)

    _score(_token(org, stream=stream), "baseline", "hads_anxiety", 10)
    _score(_token(org, stream=stream), "baseline", "hads_anxiety", 12)
    # Балл по шкале заглушки (1–4) у снятой версии — в среднее попасть не должен.
    _score(_token(org, stream=stream), "baseline", "hads_anxiety", 2, version=retired)

    overview = organization_overview(org, stream=stream)
    hads = next(i for i in overview["indicators"] if i["indicator_code"] == "hads_anxiety")

    assert hads["baseline"]["participant_count"] == 2
    assert hads["baseline"]["mean"] == 11.0  # (10 + 12) / 2, без балла 2 от снятой версии


@pytest.mark.django_db
def test_list_streams_returns_participant_counts_for_the_filter_dropdown(org):
    stream = Stream.objects.create(organization=org, code="s1", name="Поток 1")
    _token(org, stream=stream)
    _token(org, stream=stream)
    _token(org)  # без потока — не должен попасть в счётчик stream

    streams = list_streams(org)

    assert len(streams) == 1
    assert streams[0]["code"] == "s1"
    assert streams[0]["participant_count"] == 2
