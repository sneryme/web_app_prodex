"""Персональные отчёты: исторические шкалы и отдельные снимки ИИПБ v0.1.

ИИПБ доступен сразу после входного замера; сравнение — после итогового.
Нейтральные формулировки и маршрутизация определяются версией методологии.
"""
from __future__ import annotations

from django.utils import timezone

from apps.assessments.models import Question, ScoringResult
from apps.assessments.scoring import REPORT_INDICATOR_LABELS, REPORT_INDICATORS, trend_for, zone_for
from apps.assessments.iipb import EQ_DIMENSIONS, VERSION, compare_iipb
from apps.assessments.iipb_services import is_iipb, result_payload
from apps.assessments.models import IIPBResult


class ReportNotReady(Exception):
    """Нет полного замера для выдачи отчёта текущей методологии."""


# Официальные названия зон HADS из методички ("клинически/субклинически выраженная...") хранятся
# как есть в ScoringResult.interpretation_zone (apps/assessments/scoring.py:ZONE_BOUNDARIES) — это
# полезно для админки/методолога. Но участнику их показывать напрямую нельзя: PROJECT_RULES.md №1
# и ТЗ FR-08.4 прямо запрещают слово «клиническая» и всё, что звучит как диагноз. Поэтому в
# персональном отчёте (но не в БД) зона проходит через эту смягчённую формулировку.
# ВАЖНО: конкретные формулировки — черновые, не согласованы с методологом/неймингом бренда;
# при ревью стоит свериться с тем, как PRODEX обычно говорит об этом с участниками.
PARTICIPANT_ZONE_LABELS = {
    "субклинически выраженная тревога": "повышенная тревожность",
    "клинически выраженная тревога": "высокая тревожность",
    "субклинически выраженная депрессия": "сниженный эмоциональный фон",
    "клинически выраженная депрессия": "выраженно сниженный эмоциональный фон",
}


def _participant_zone_label(zone: str) -> str:
    return PARTICIPANT_ZONE_LABELS.get(zone, zone)


def _eq5d_profile(token, bundle=None) -> list[dict]:
    """Измерения EQ-5D кроме VAS — расшифровка вместо кода, не входят в 5 карточек (ТЗ FR-08.5)."""
    version_ids = ScoringResult.objects.filter(token=token, bundle=bundle).values_list("questionnaire_version_id", flat=True)
    profile_questions = Question.objects.filter(questionnaire_version__code="eq5d", questionnaire_version_id__in=version_ids)
    if bundle is not None:
        profile_questions = profile_questions.filter(questionnaire_version__bundle_items__bundle=bundle)
    profile_questions = profile_questions.exclude(indicator_code="eq5d_vas").order_by("order")

    baseline = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, bundle=bundle, stage="baseline")}
    followup = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, bundle=bundle, stage="followup")}

    profile = []
    for question in profile_questions:
        before = baseline.get(question.indicator_code)
        after = followup.get(question.indicator_code)
        if before is None or after is None:
            continue
        profile.append(
            {
                "indicator_code": question.indicator_code,
                "label": question.text,
                "before": float(before.raw_score),
                "after": float(after.raw_score),
            }
        )
    return profile


def _summary_text(trends: list[str]) -> str:
    improved = trends.count("improved")
    worsened = trends.count("worsened")
    total = len(trends)
    if improved == 0 and worsened == 0:
        return "По большинству показателей существенных изменений не выявлено."
    if worsened == 0:
        return f"По итогам повторного тестирования отмечается положительная динамика ({improved} из {total} показателей)."
    if improved == 0:
        return "По результатам повторного тестирования отмечается отрицательная динамика по части показателей."
    return "Результаты имеют разнонаправленную динамику: часть показателей улучшилась, часть — нет."


def build_personal_report(token, bundle=None) -> dict:
    if is_iipb(bundle):
        return _build_iipb_report(token, bundle)
    baseline = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, bundle=bundle, stage="baseline")}
    followup = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, bundle=bundle, stage="followup")}

    indicators = [code for code in REPORT_INDICATORS if code in baseline and code in followup]
    if not indicators:
        raise ReportNotReady

    cards = []
    trends = []
    for code in indicators:
        before = baseline[code]
        after = followup[code]
        trend = trend_for(code, before.raw_score, after.raw_score)
        trends.append(trend)
        cards.append(
            {
                "indicator_code": code,
                "label": REPORT_INDICATOR_LABELS[code],
                "before": {"raw_score": float(before.raw_score), "zone": _participant_zone_label(before.interpretation_zone)},
                "after": {"raw_score": float(after.raw_score), "zone": _participant_zone_label(after.interpretation_zone)},
                "change": float(after.raw_score) - float(before.raw_score),
                "trend": trend,
            }
        )

    payload = {
        "token": token.token,
        "is_test": token.is_test,
        "bundle_id": bundle.pk if bundle else None,
        "bundle_name": bundle.name if bundle else "",
        "summary": _summary_text(trends),
        "improved_count": trends.count("improved"),
        "total_count": len(trends),
        "cards": cards,
        "eq5d_profile": _eq5d_profile(token, bundle),
    }

    # Кэш для будущей повторной выдачи без пересчёта; ScoringResult остаётся источником истины,
    # это поле — просто последний собранный снимок (apps.participants.ParticipantToken).
    token.report_payload = payload
    token.report_generated_at = timezone.now()
    token.save(update_fields=["report_payload", "report_generated_at"])
    return payload


def _build_iipb_report(token, bundle):
    measurements = {r.stage: result_payload(r) for r in IIPBResult.objects.filter(token=token, bundle=bundle, version=VERSION)}
    before = measurements.get("baseline")
    if before is None:
        raise ReportNotReady
    after = measurements.get("followup")
    dynamics = compare_iipb(before, after) if after else None
    cards = []
    # ЛТ выводится в маркере каждого замера и не участвует в динамике (§5.4).
    if after:
        for code in REPORT_INDICATORS:
            if code == "trait_anxiety":
                continue
            before_value, after_value = before["inputs"][code], after["inputs"][code]
            cards.append({
                "indicator_code": code, "label": REPORT_INDICATOR_LABELS[code],
                "before": {"raw_score": before_value, "zone": "" if code == "eq5d_vas" else _participant_zone_label(zone_for(code, before_value))},
                "after": {"raw_score": after_value, "zone": "" if code == "eq5d_vas" else _participant_zone_label(zone_for(code, after_value))},
                "change": after_value - before_value, "trend": trend_for(code, before_value, after_value),
            })
    payload = {
        "token": token.token, "bundle_id": bundle.pk, "bundle_name": bundle.name,
        "is_test": token.is_test,
        "methodology": bundle.methodology, "status": "completed" if after else "baseline_only",
        "summary": dynamics["summary"] if dynamics else before["conclusion"],
        "improved_count": sum(card["trend"] == "improved" for card in cards), "total_count": len(cards),
        "cards": cards,
        "eq5d_profile": [
            {"indicator_code": code, "label": label, "before": before["inputs"][code], "after": after["inputs"][code]}
            for code, label in zip(EQ_DIMENSIONS, ["Подвижность", "Уход за собой", "Повседневная деятельность", "Боль / дискомфорт", "Тревога / депрессия"])
        ] if after else [],
        "iipb": {"baseline": before, "followup": after, "dynamics": dynamics},
        "routing_contacts": {"specialist": token.organization.specialist_contact, "physician": token.organization.physician_contact},
    }
    token.report_payload = payload
    token.report_generated_at = timezone.now()
    token.save(update_fields=["report_payload", "report_generated_at"])
    return payload
