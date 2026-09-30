"""Черновой scoring-движок (ТЗ FR-07).

Формулы и границы зон здесь НЕ являются реальными клиническими шкалами — это временная
механика «ответы → балл → зона», чтобы можно было проверить весь путь участника и
персональный отчёт (FR-08), не дожидаясь методолога. Реальные формулы EQ-5D,
Спилбергера–Ханина и HADS и границы зон интерпретации проходят методологическое
подтверждение (PROJECT_RULES.md №5) и подставляются сюда без изменения интерфейса функций.
"""
from __future__ import annotations

from decimal import Decimal

from .models import AnswerResponse, Question, ScoringResult

# 5 отчётных показателей персонального отчёта (ТЗ FR-08.1). Остальные измерения EQ-5D
# (например eq5d_mobility) в это множество не входят — они образуют отдельный «профиль
# здоровья», а не одну из пяти карточек (ТЗ FR-08.5), и не объединяются в общий индекс
# (PROJECT_RULES.md №2).
REPORT_INDICATORS = [
    "eq5d_vas",
    "situational_anxiety",
    "trait_anxiety",
    "hads_anxiety",
    "hads_depression",
]

REPORT_INDICATOR_LABELS = {
    "eq5d_vas": "Самооценка здоровья (EQ-5D VAS)",
    "situational_anxiety": "Ситуативная тревожность",
    "trait_anxiety": "Личностная тревожность",
    "hads_anxiety": "Тревога по шкале HADS",
    "hads_depression": "Депрессивная симптоматика HADS",
}

# high_is_good — чем выше балл, тем лучше (самооценка здоровья).
# high_is_bad — чем выше балл, тем хуже (шкалы тревожности и депрессии).
INDICATOR_DIRECTION = {
    "eq5d_vas": "high_is_good",
    "situational_anxiety": "high_is_bad",
    "trait_anxiety": "high_is_bad",
    "hads_anxiety": "high_is_bad",
    "hads_depression": "high_is_bad",
}

_BAD_DIRECTION_ZONES = ["низкая", "умеренная", "высокая", "выраженная"]
_GOOD_DIRECTION_ZONES = ["низкая", "удовлетворительная", "хорошая", "отличная"]


def max_possible_score(indicator_code: str) -> int:
    """Сумма максимальных баллов по всем активным вопросам показателя (для доли/зоны)."""
    total = 0
    for question in Question.objects.filter(indicator_code=indicator_code, questionnaire_version__is_active=True):
        best_option = question.options.order_by("-value").first()
        if best_option:
            total += best_option.value
    return total or 1


def zone_for(indicator_code: str, raw_score: Decimal | int | float) -> str:
    """Черновая (не клиническая) классификация зоны по доле от максимума шкалы."""
    max_score = max_possible_score(indicator_code)
    ratio = float(raw_score) / max_score if max_score else 0.0
    zones = _GOOD_DIRECTION_ZONES if INDICATOR_DIRECTION.get(indicator_code) == "high_is_good" else _BAD_DIRECTION_ZONES
    if ratio <= 0.25:
        index = 0
    elif ratio <= 0.5:
        index = 1
    elif ratio <= 0.75:
        index = 2
    else:
        index = 3
    return zones[index]


def trend_for(indicator_code: str, before: Decimal, after: Decimal) -> str:
    """"improved" | "worsened" | "stable" — с учётом направления шкалы показателя."""
    change = float(after) - float(before)
    if change == 0:
        return "stable"
    increased_is_good = INDICATOR_DIRECTION.get(indicator_code, "high_is_bad") == "high_is_good"
    improved = (change > 0) == increased_is_good
    return "improved" if improved else "worsened"


def compute_scores_for_stage(token, stage) -> list[ScoringResult]:
    """ТЗ FR-07: автоматический scoring по всем показателям, отвеченным на этапе `stage`."""
    answers = (
        AnswerResponse.objects.filter(token=token, stage=stage, selected_option__isnull=False)
        .select_related("question", "selected_option")
    )
    totals: dict[str, int] = {}
    for answer in answers:
        code = answer.question.indicator_code
        totals[code] = totals.get(code, 0) + answer.selected_option.value

    results = []
    for indicator_code, raw_score in totals.items():
        result, _ = ScoringResult.objects.update_or_create(
            token=token,
            stage=stage,
            indicator_code=indicator_code,
            defaults={"raw_score": Decimal(raw_score), "interpretation_zone": zone_for(indicator_code, raw_score)},
        )
        results.append(result)
    return results
