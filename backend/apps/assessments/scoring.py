"""Scoring-движок (ТЗ FR-07).

Границы зон HADS и Спилбергера–Ханина — реальные клинические отрезки из методички
(`project/` → файл методолога "4 теста для бота..."), а не черновая эвристика. EQ-5D VAS
границ зон в методичке не задано (это визуальная аналоговая шкала самооценки, не клиническая
шкала с cut-off'ами) — для неё и для вспомогательных измерений EQ-5D (`eq5d_mobility` и т.п.,
не входящих в 5 отчётных карточек, см. ниже) используется черновая классификация по доле от
максимума шкалы, как и раньше.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from .models import AnswerResponse, Question, ScoringResult

logger = logging.getLogger(__name__)

# 5 отчётных показателей персонального отчёта (ТЗ FR-08.1). Остальные измерения EQ-5D
# (например eq5d_mobility) в это множество не входят — они образуют отдельный «профиль
# здоровья», а не одну из пяти карточек (ТЗ FR-08.5). ИИПБ рассчитывается отдельно
# только для комплекта с явно указанной версией методологии.
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

# Границы зон из методички, одинаковые по форме для HADS (0–21 по каждой подшкале) и шкалы
# Спилбергера–Ханина (20–80 по каждому блоку): список (верхняя_граница_включительно, метка),
# последняя граница — None (всё, что выше предыдущей).
ZONE_BOUNDARIES: dict[str, list[tuple[int | None, str]]] = {
    "hads_anxiety": [(7, "норма"), (10, "субклинически выраженная тревога"), (None, "клинически выраженная тревога")],
    "hads_depression": [
        (7, "норма"),
        (10, "субклинически выраженная депрессия"),
        (None, "клинически выраженная депрессия"),
    ],
    "situational_anxiety": [(30, "низкая"), (44, "умеренная"), (None, "высокая")],
    "trait_anxiety": [(30, "низкая"), (44, "умеренная"), (None, "высокая")],
}

# Максимум шкалы для показателей без вариантов ответа (свободный числовой ввод вроде EQ-5D VAS,
# где max_possible_score() по вопросам с вариантами посчитать нельзя — их просто нет).
FIXED_MAX = {"eq5d_vas": 100}

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
    """Зона по показателю: реальные клинические границы, если они заданы методичкой, иначе
    черновая классификация по доле от максимума шкалы (EQ-5D VAS и профильные измерения)."""
    boundaries = ZONE_BOUNDARIES.get(indicator_code)
    if boundaries:
        score = float(raw_score)
        for cutoff, label in boundaries:
            if cutoff is None or score <= cutoff:
                return label

    max_score = FIXED_MAX.get(indicator_code) or max_possible_score(indicator_code)
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


def compute_scores_for_stage(token, stage, bundle=None) -> list[ScoringResult]:
    """ТЗ FR-07: автоматический scoring по всем показателям, отвеченным на этапе `stage`.

    Большинство вопросов — выбор карточки (`selected_option.value`). EQ-5D VAS — исключение:
    это не карточка, а свободный числовой ввод 0–100 (`raw_value`), который сам и есть балл
    показателя, а не слагаемое в сумме карточек.
    """
    answers = AnswerResponse.objects.filter(token=token, stage=stage, bundle=bundle).select_related("question", "selected_option")
    totals: dict[str, int] = {}
    # Версия методики, которой получен балл (Положение о ролях, п. 5.2) — берётся из самого вопроса,
    # поэтому у каждого показателя она своя: EQ-5D, HADS и СШХ это разные QuestionnaireVersion.
    versions: dict[str, set[int]] = {}
    for answer in answers:
        code = answer.question.indicator_code
        versions.setdefault(code, set()).add(answer.question.questionnaire_version_id)
        if answer.selected_option is not None:
            totals[code] = totals.get(code, 0) + answer.selected_option.value
        elif answer.raw_value:
            try:
                totals[code] = totals.get(code, 0) + int(answer.raw_value)
            except ValueError:
                continue

    results = []
    for indicator_code, raw_score in totals.items():
        version_ids = versions[indicator_code]
        if len(version_ids) > 1:
            # Ответы одного показателя относятся к разным версиям опросника — сумма посчитана по
            # смешанной шкале и не принадлежит ни одной версии. Такое возможно только у исторических
            # данных (когда одновременно были активны и заглушка, и реальная методика);
            # `seed_real_questionnaires` теперь деактивирует все прочие версии. Балл не сохраняем:
            # лучше отсутствие записи, чем молча приписанная не та версия. Исключение не поднимаем —
            # этот код выполняется внутри сохранения ответа участником, и падать там нельзя.
            logger.warning(
                "Пропущен scoring: token=%s stage=%s показатель=%s, ответы из версий %s — "
                "смешанная шкала. Разберите данные через manage.py recompute_scores.",
                token.pk,
                stage,
                indicator_code,
                sorted(version_ids),
            )
            continue
        result, _ = ScoringResult.objects.update_or_create(
            token=token,
            bundle=bundle,
            stage=stage,
            indicator_code=indicator_code,
            defaults={
                "raw_score": Decimal(raw_score),
                "interpretation_zone": (
                    "" if bundle and bundle.methodology == "iipb-0.1" and indicator_code.startswith("eq5d_")
                    else zone_for(indicator_code, raw_score)
                ),
                "questionnaire_version_id": next(iter(version_ids)),
            },
        )
        results.append(result)
    from .iipb_services import save_iipb_result
    save_iipb_result(token, stage, bundle)
    return results
