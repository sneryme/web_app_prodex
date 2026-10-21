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

from apps.assessments.models import ScoringResult
from apps.assessments.scoring import REPORT_INDICATOR_LABELS, REPORT_INDICATORS, trend_for
from apps.organizations.models import Stream
from apps.participants.models import ParticipantToken

DEFAULT_GROUP_THRESHOLD = 5


def list_streams(organization) -> list[dict]:
    streams = Stream.objects.filter(organization=organization).order_by("code")
    return [
        {
            "id": stream.id,
            "code": stream.code,
            "name": stream.name,
            "status": stream.status,
            "participant_count": ParticipantToken.objects.filter(stream=stream).count(),
        }
        for stream in streams
    ]


def _published_results(tokens, **filters):
    """Баллы только действующей версии методики (Положение о ролях, п. 5.2).

    Без этого фильтра агрегат складывает в одну группу по `indicator_code` баллы, посчитанные по
    разным версиям опросника: шкала реального HADS (0–21) и шкала опросника-заглушки (1–4) дают
    один и тот же код показателя. Среднее по такой смеси не значит ничего. Строки с пустой версией
    (исторические, чьи ответы уже удалены) тоже исключаются — их шкалу подтвердить нечем.
    """
    return ScoringResult.objects.filter(token__in=tokens, questionnaire_version__is_active=True, **filters)


def _stage_block(indicator_code: str, stage: str, tokens, threshold: int) -> dict:
    results = _published_results(tokens, stage=stage, indicator_code=indicator_code)
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


def _trend_block(indicator_code: str, tokens, threshold: int) -> dict:
    baseline_by_token = {
        r.token_id: r.raw_score
        for r in _published_results(tokens, stage="baseline", indicator_code=indicator_code)
    }
    followup_by_token = {
        r.token_id: r.raw_score
        for r in _published_results(tokens, stage="followup", indicator_code=indicator_code)
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


def organization_overview(organization, stream=None) -> dict:
    """Один вызов — весь дашборд: охват, completion, 5 показателей с распределением «вход/итог»."""
    tokens = ParticipantToken.objects.filter(organization=organization)
    if stream is not None:
        tokens = tokens.filter(stream=stream)

    threshold = stream.min_group_size if stream is not None else DEFAULT_GROUP_THRESHOLD

    indicators = [
        {
            "indicator_code": code,
            "label": REPORT_INDICATOR_LABELS[code],
            "baseline": _stage_block(code, "baseline", tokens, threshold),
            "followup": _stage_block(code, "followup", tokens, threshold),
            "trend": _trend_block(code, tokens, threshold),
        }
        for code in REPORT_INDICATORS
    ]

    return {
        "organization": {"id": organization.id, "name": organization.name},
        "stream": {"id": stream.id, "code": stream.code, "name": stream.name} if stream else None,
        "coverage": {"participants": tokens.count()},
        "completion": {
            "baseline_completed": tokens.filter(baseline_status=ParticipantToken.PROGRESS_COMPLETED).count(),
            "followup_completed": tokens.filter(followup_status=ParticipantToken.PROGRESS_COMPLETED).count(),
        },
        "indicators": indicators,
    }
