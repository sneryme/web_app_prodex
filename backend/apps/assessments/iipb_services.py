"""Версионированные снимки полного замера. Исторические ответы не переинтерпретируются."""
from django.db.models import Max

from .iipb import InvalidIIPBInput, METHODOLOGY, VERSION, VERSION_DATE, calculate_iipb
from .models import AnswerResponse, IIPBResult, ScoringResult


def is_iipb(bundle):
    return bundle is not None and bundle.methodology == METHODOLOGY


def save_iipb_result(token, stage, bundle):
    if not is_iipb(bundle):
        return None
    existing = IIPBResult.objects.filter(token=token, bundle=bundle, stage=stage, version=VERSION).first()
    if existing:
        return existing
    # Прежний EQ-5D-3L имеет те же коды показателей. Диапазон 1–5 сам по себе
    # не отличает его от 5L; происхождение трёх форм проверяется явно.
    versions = set(bundle.items.values_list("questionnaire_version__code", "questionnaire_version__version_label"))
    if versions != {(code, METHODOLOGY) for code in ("hads", "stai", "eq5d")}:
        return None
    expected = set(bundle.items.values_list("questionnaire_version__questions__id", flat=True))
    expected.discard(None)
    answers = AnswerResponse.objects.filter(token=token, bundle=bundle, stage=stage)
    if not expected or set(answers.values_list("question_id", flat=True)) != expected:
        return None
    results = list(ScoringResult.objects.filter(token=token, bundle=bundle, stage=stage))
    try:
        payload = calculate_iipb({r.indicator_code: r.raw_score for r in results})
    except InvalidIIPBInput:
        return None
    payload["questionnaire_versions"] = {
        str(r.questionnaire_version_id): r.questionnaire_version.version_label
        for r in results if r.questionnaire_version_id is not None
    }
    measured_at = answers.aggregate(value=Max("answered_at"))["value"]
    result, _ = IIPBResult.objects.get_or_create(
        token=token, bundle=bundle, stage=stage, version=VERSION,
        defaults={"version_date": VERSION_DATE, "index": payload["index"], "level": payload["level"],
                  "payload": payload, "measured_at": measured_at},
    )
    return result


def result_payload(result):
    return {**result.payload, "measured_at": result.measured_at.isoformat()} if result else None
