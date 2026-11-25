"""Групповые агрегаты для дашборда работодателя (ТЗ FR-09).

Отдельно от `services.py` (персональный отчёт участника, FR-08) — разные аудитории и разные
правила показа: здесь никогда нет токена/ответов отдельного человека (ТЗ FR-09.5), только счётчики
и средние по группе. Малые группы (меньше порога публикации) скрываются (ТЗ FR-09.4) —
см. `Stream.min_group_size`; для агрегата по всей организации (без фильтра по потоку) готового
порога в модели нет, используется тот же дефолт, что и у потока — см. `DEFAULT_GROUP_THRESHOLD`.

Результат не кэшируется в `AggregateSnapshot` (хотя модель для этого существует) — пересчитывается
заново при каждом обращении, чтобы не городить дедупликацию при отсутствии уникального индекса на
`AggregateSnapshot` (nullable `stream` — NULL не защищает от дублей в Postgres). Если понадобится
кэш/история для экспорта (ТЗ FR-10), эту функцию можно дополнить записью снимка.
"""
from __future__ import annotations

from collections import Counter

from django.db.models import Count

from apps.assessments.models import AnswerResponse, ScoringResult, TestBundle
from apps.assessments.scoring import REPORT_INDICATOR_LABELS, REPORT_INDICATORS, trend_for
from apps.organizations.models import Stream
from apps.participants.models import ParticipantToken
from apps.assessments.iipb_services import is_iipb
from .iipb_services import iipb_overview

DEFAULT_GROUP_THRESHOLD = 5


def list_streams(organization) -> list[dict]:
    streams = Stream.objects.filter(organization=organization).order_by("name", "pk")
    return [
        {
            "id": stream.id,
            "code": stream.code,
            "name": stream.name,
            "status": stream.status,
            "participant_count": ParticipantToken.objects.filter(stream=stream, is_test=False).count(),
        }
        for stream in streams
    ]


def list_bundles(organization) -> list[dict]:
    return [
        {"id": bundle.id, "code": bundle.code, "name": bundle.name}
        for bundle in organization.test_bundles.order_by("-methodology", "name", "id")
    ]


def _published_results(tokens, bundle=None, **filters):
    """Баллы только действующей версии методики (Положение о ролях, п. 5.2).

    Без этого фильтра агрегат складывает в одну группу по `indicator_code` баллы, посчитанные по
    разным версиям опросника: шкала реального HADS (0–21) и шкала опросника-заглушки (1–4) дают
    один и тот же код показателя. Среднее по такой смеси не значит ничего. Строки с пустой версией
    (исторические, чьи ответы уже удалены) тоже исключаются — их шкалу подтвердить нечем.
    """
    results = ScoringResult.objects.filter(token__in=tokens, token__is_test=False, **filters)
    if bundle is not None:
        results = results.filter(bundle=bundle, questionnaire_version__bundle_items__bundle=bundle)
    else:
        results = results.filter(bundle__isnull=True, questionnaire_version__is_active=True)
    return results


def _stage_block(indicator_code: str, stage: str, tokens, threshold: int, bundle=None) -> dict:
    results = _published_results(tokens, bundle=bundle, stage=stage, indicator_code=indicator_code)
    count = results.count()
    if count < threshold:
        # ТЗ FR-09.4: ни среднего, ни распределения — только то, что группа слишком мала.
        return {"participant_count": count, "is_suppressed": True}

    scores = [float(r.raw_score) for r in results]
    distribution = Counter(r.interpretation_zone for r in results)
    return {
        "participant_count": count,
        "is_suppressed": False,
        "mean": round(sum(scores) / len(scores), 2),
        "zone_distribution": dict(distribution),
    }


def _trend_block(indicator_code: str, tokens, threshold: int, bundle=None) -> dict:
    baseline_by_token = {
        r.token_id: r.raw_score
        for r in _published_results(tokens, bundle=bundle, stage="baseline", indicator_code=indicator_code)
    }
    followup_by_token = {
        r.token_id: r.raw_score
        for r in _published_results(tokens, bundle=bundle, stage="followup", indicator_code=indicator_code)
    }
    trends = [
        trend_for(indicator_code, before, followup_by_token[token_id])
        for token_id, before in baseline_by_token.items()
        if token_id in followup_by_token
    ]
    if len(trends) < threshold:
        return {"paired_count": len(trends), "is_suppressed": True}
    return {
        "paired_count": len(trends),
        "is_suppressed": False,
        "improved": trends.count("improved"),
        "worsened": trends.count("worsened"),
        "stable": trends.count("stable"),
    }


def organization_overview(organization, stream=None, bundle=None) -> dict:
    """Один вызов — весь дашборд: охват, completion, 5 показателей с распределением «вход/итог»."""
    if bundle is None:
        bundle = organization.test_bundles.order_by("-methodology", "name", "id").first()
    tokens = ParticipantToken.objects.filter(organization=organization)
    if stream is not None:
        tokens = tokens.filter(stream=stream)
    threshold = stream.min_group_size if stream is not None else DEFAULT_GROUP_THRESHOLD
    if is_iipb(bundle):
        threshold = max(5, threshold)
    return _overview_for_tokens(organization, tokens, bundle, stream, threshold)


def _overview_for_tokens(organization, tokens, bundle, stream, threshold: int) -> dict:
    tokens = tokens.filter(is_test=False)
    total_questions = 0
    if bundle is not None:
        total_questions = sum(
            item.questionnaire_version.questions.count()
            for item in bundle.items.all()
        )
        token_ids = AnswerResponse.objects.filter(bundle=bundle, token__in=tokens).values_list("token_id", flat=True).distinct()
        tokens = tokens.filter(pk__in=token_ids)

    indicators = [
        {
            "indicator_code": code,
            "label": REPORT_INDICATOR_LABELS[code],
            "baseline": _stage_block(code, "baseline", tokens, threshold, bundle=bundle),
            "followup": _stage_block(code, "followup", tokens, threshold, bundle=bundle),
            "trend": _trend_block(code, tokens, threshold, bundle=bundle),
        }
        for code in REPORT_INDICATORS
        if not is_iipb(bundle) or code != "trait_anxiety"
    ]

    return {
        "organization": {"id": organization.id, "name": organization.name},
        "bundle": {"id": bundle.id, "code": bundle.code, "name": bundle.name} if bundle else None,
        "stream": {"id": stream.id, "code": stream.code, "name": stream.name} if stream else None,
        "coverage": {"participants": tokens.count()},
        "completion": {
            "baseline_completed": _completed_bundle_stage(tokens, bundle, "baseline", total_questions),
            "followup_completed": _completed_bundle_stage(tokens, bundle, "followup", total_questions),
        },
        "indicators": indicators,
        "iipb": iipb_overview(tokens, bundle, threshold) if is_iipb(bundle) else None,
    }


def compare_streams(organization, stream_ids: list[int], bundle=None) -> list[dict]:
    """Сравнивает 2–4 потока, применяя индивидуальный порог публикации каждого потока."""
    if bundle is None:
        bundle = organization.test_bundles.order_by("-methodology", "name", "id").first()
    streams = list(Stream.objects.filter(organization=organization, pk__in=stream_ids).order_by("name", "pk"))
    if len(streams) != len(set(stream_ids)):
        raise ValueError("One or more streams do not belong to this organization.")
    return [
        {
            "key": f"stream-{stream.pk}",
            "label": stream.name or f"Поток {stream.pk}",
            "threshold": max(5, stream.min_group_size) if is_iipb(bundle) else stream.min_group_size,
            "overview": organization_overview(organization, stream=stream, bundle=bundle),
        }
        for stream in streams
    ]


def compare_periods(organization, period_ranges: list[dict], bundle=None) -> list[dict]:
    """Сравнивает непересекающиеся когорты по дате создания сессии участника."""
    if bundle is None:
        bundle = organization.test_bundles.order_by("-methodology", "name", "id").first()
    groups = []
    for index, period in enumerate(period_ranges, start=1):
        tokens = ParticipantToken.objects.filter(
            organization=organization,
            created_at__date__gte=period["from"],
            created_at__date__lte=period["to"],
        )
        groups.append(
            {
                "key": f"period-{index}",
                "label": period["label"],
                "date_from": period["from"].isoformat(),
                "date_to": period["to"].isoformat(),
                "threshold": DEFAULT_GROUP_THRESHOLD,
                "overview": _overview_for_tokens(organization, tokens, bundle, None, DEFAULT_GROUP_THRESHOLD),
            }
        )
    return groups


def _completed_bundle_stage(tokens, bundle, stage: str, total_questions: int) -> int:
    if bundle is None:
        field = "baseline_status" if stage == "baseline" else "followup_status"
        return tokens.filter(**{field: ParticipantToken.PROGRESS_COMPLETED}).count()
    if total_questions == 0:
        return 0
    return (
        AnswerResponse.objects.filter(token__in=tokens, bundle=bundle, stage=stage)
        .values("token_id")
        .annotate(answer_count=Count("question_id", distinct=True))
        .filter(answer_count__gte=total_questions)
        .count()
    )
