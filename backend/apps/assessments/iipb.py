"""ИИПБ v0.1 (16.11.2026), разделы 4–6 и приложение Б рекомендаций.

Чистая расчётная функция: десять обязательных целочисленных входов, без импутации.
Нормировка, веса и округление совпадают с приложенным Excel-калькулятором.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

METHODOLOGY = "iipb-0.1"
VERSION = "0.1"
VERSION_DATE = "2026-11-16"
NOTICE = (
    "ИИПБ v0.1 — предварительная, не валидированная конструкция. "
    "Результат не является диагнозом и не заменяет консультацию специалиста."
)
DYNAMICS_NOTICE = (
    "Порог достоверного изменения ИИПБ не установлен. "
    "Без контрольной группы изменение нельзя приписать терапии."
)
EQ_DIMENSIONS = (
    "eq5d_mobility", "eq5d_self_care", "eq5d_daily_activities",
    "eq5d_pain", "eq5d_anxiety_depression",
)
RANGES = {
    "hads_anxiety": (0, 21), "hads_depression": (0, 21),
    "situational_anxiety": (20, 80), "trait_anxiety": (20, 80),
    **{code: (1, 5) for code in EQ_DIMENSIONS}, "eq5d_vas": (0, 100),
}
ANCHORS = {
    "hads_anxiety": ((0, 100), (7, 75), (10, 50), (21, 0)),
    "hads_depression": ((0, 100), (7, 75), (10, 50), (21, 0)),
    "situational_anxiety": ((20, 100), (30, 75), (44, 50), (80, 0)),
    "lss": ((5, 100), (7, 75), (10, 50), (25, 0)),
    "eq5d_vas": ((0, 0), (40, 50), (57, 75), (100, 100)),
}
LEVELS = (
    (75, "I", "Сохранное благополучие", "Профилактический курс по графику."),
    (50, "II", "Лёгкое снижение", "Курс; повторная оценка после курса."),
    (25, "III", "Умеренное снижение", "Курс и консультация специалиста."),
    (0, "IV", "Выраженное снижение", "Консультация специалиста до курса или вместо него."),
)
SPECIALIST_ACTION = "Обратитесь к врачу-психотерапевту, врачу-психиатру или медицинскому психологу."


class InvalidIIPBInput(ValueError):
    pass


def normalize(value, anchors):
    value = Decimal(str(value))
    if value <= anchors[0][0]:
        return Decimal(anchors[0][1])
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if value <= x1:
            return Decimal(y0) + Decimal(y1 - y0) * (value - x0) / Decimal(x1 - x0)
    return Decimal(anchors[-1][1])


def calculate_iipb(values: dict) -> dict:
    scores = {}
    for code, (minimum, maximum) in RANGES.items():
        try:
            value = Decimal(str(values[code]))
            if isinstance(values[code], bool) or not value.is_finite() or value != value.to_integral_value():
                raise InvalidIIPBInput(code)
            if not minimum <= value <= maximum:
                raise InvalidIIPBInput(code)
        except (KeyError, InvalidOperation, TypeError, ValueError):
            raise InvalidIIPBInput(f"{code}: требуется целое число {minimum}–{maximum}") from None
        scores[code] = int(value)

    lss = sum(scores[code] for code in EQ_DIMENSIONS)
    subindices = {
        code: normalize(lss if code == "lss" else scores[code], anchors)
        for code, anchors in ANCHORS.items()
    }
    domains = {
        "anxiety": (subindices["hads_anxiety"] + subindices["situational_anxiety"]) / 2,
        "depression": subindices["hads_depression"],
        "health": (subindices["lss"] + subindices["eq5d_vas"]) / 2,
    }
    mean = sum(domains.values()) / 3
    index = int(mean.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    _, level, label, action = next(row for row in LEVELS if index >= row[0])
    red_flags, yellow_flags = [], []
    for condition, code, text in (
        (scores["hads_anxiety"] >= 11, "R1", "Повышенный показатель тревоги HADS"),
        (scores["hads_depression"] >= 11, "R2", "Сниженный эмоциональный фон по HADS"),
        (scores["eq5d_anxiety_depression"] >= 4, "R3", "Выраженные трудности в измерении EQ-5D «Тревога / депрессия»"),
    ):
        if condition:
            red_flags.append({"code": code, "label": text, "action": SPECIALIST_ACTION})
    for condition, code, text, flag_action in (
        (scores["situational_anxiety"] >= 45, "Y1", "Высокая ситуативная тревожность", "Повторите оценку через 1–2 недели. Если признак сохраняется, обратитесь к специалисту."),
        (scores["eq5d_vas"] < 40, "Y2", "Низкая самооценка здоровья", "Обратитесь к терапевту для оценки возможных соматических причин."),
        (max(scores[code] for code in EQ_DIMENSIONS[:4]) >= 4, "Y3", "Выраженные трудности в профиле здоровья", "Обратитесь к терапевту."),
    ):
        if condition:
            yellow_flags.append({"code": code, "label": text, "action": flag_action})
    trait = scores["trait_anxiety"]
    return {
        "version": VERSION, "version_date": VERSION_DATE, "notice": NOTICE,
        "inputs": scores, "lss": lss,
        "subindices": {code: float(value) for code, value in subindices.items()},
        "domains": {code: float(value) for code, value in domains.items()},
        "unrounded_index": float(mean), "index": index,
        "level": level, "level_label": label,
        "conclusion": "Требуется консультация специалиста" if red_flags else label,
        "action": SPECIALIST_ACTION if red_flags else action,
        "red_flags": red_flags, "yellow_flags": yellow_flags,
        "trait_marker": {"raw_score": trait, "label": "низкая" if trait <= 30 else "умеренная" if trait <= 44 else "высокая"},
    }


def compare_iipb(before: dict, after: dict) -> dict:
    if (before["version"], before["version_date"]) != (after["version"], after["version_date"]):
        raise ValueError("Нельзя сравнивать разные версии ИИПБ")
    delta = after["index"] - before["index"]
    relative = None if before["index"] == 0 else float(
        (Decimal(delta) * 100 / Decimal(before["index"])).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )
    trend = "improved" if delta > 0 else "worsened" if delta < 0 else "stable"
    direction = {"improved": "Улучшение", "worsened": "Ухудшение", "stable": "Без изменений"}[trend]
    actions = []
    if after["red_flags"]:
        actions.append(SPECIALIST_ACTION)
    if [r[1] for r in LEVELS].index(after["level"]) > [r[1] for r in LEVELS].index(before["level"]):
        actions.append("Уровень благополучия снизился. Обратитесь к специалисту.")
    persisted = {f["code"] for f in before["yellow_flags"]} & {f["code"] for f in after["yellow_flags"]}
    if "Y1" in persisted:
        actions.append("Высокая ситуативная тревожность сохраняется. Обратитесь к специалисту.")
    if persisted & {"Y2", "Y3"}:
        actions.append("Признаки соматического неблагополучия сохраняются. Обратитесь к терапевту.")
    return {
        "delta_pp": delta, "delta_percent": relative,
        "level_change": f'{before["level"]} → {after["level"]}', "trend": trend,
        "summary": f"{direction}: {delta:+d} п.п. " + (f"({relative:+.1f}%). " if relative is not None else "(относительное изменение не рассчитывается: исходно 0). ") + DYNAMICS_NOTICE,
        "notice": DYNAMICS_NOTICE, "actions": actions,
    }
