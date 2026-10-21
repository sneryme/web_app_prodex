"""Сборка персонального отчёта «до/после» (ТЗ FR-08) из посчитанных ScoringResult.

Текст — нейтральные черновые формулировки, не диагноз (ТЗ FR-08.4). Показатели не
объединяются в общий индекс (PROJECT_RULES.md №2): у отчёта нет ни одного числа,
которое суммировало бы EQ-5D, HADS и Спилбергера–Ханина вместе.
"""
from __future__ import annotations

from django.utils import timezone

from apps.assessments.models import Question, ScoringResult
from apps.assessments.scoring import REPORT_INDICATOR_LABELS, REPORT_INDICATORS, trend_for


class ReportNotReady(Exception):
    """Отчёт формируется только после завершения обоих этапов (ТЗ FR-04.4)."""


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


def _eq5d_profile(token) -> list[dict]:
    """Измерения EQ-5D кроме VAS — расшифровка вместо кода, не входят в 5 карточек (ТЗ FR-08.5)."""
    profile_questions = (
        Question.objects.filter(questionnaire_version__code="eq5d", questionnaire_version__is_active=True)
        .exclude(indicator_code="eq5d_vas")
        .order_by("order")
    )

    baseline = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, stage="baseline")}
    followup = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, stage="followup")}

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


def build_personal_report(token) -> dict:
    baseline = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, stage="baseline")}
    followup = {r.indicator_code: r for r in ScoringResult.objects.filter(token=token, stage="followup")}

    missing = [code for code in REPORT_INDICATORS if code not in baseline or code not in followup]
    if missing:
        raise ReportNotReady

    cards = []
    trends = []
    for code in REPORT_INDICATORS:
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
        "summary": _summary_text(trends),
        "improved_count": trends.count("improved"),
        "total_count": len(trends),
        "cards": cards,
        "eq5d_profile": _eq5d_profile(token),
    }

    # Кэш для будущей повторной выдачи без пересчёта; ScoringResult остаётся источником истины,
    # это поле — просто последний собранный снимок (apps.participants.ParticipantToken).
    token.report_payload = payload
    token.report_generated_at = timezone.now()
    token.save(update_fields=["report_payload", "report_generated_at"])
    return payload
