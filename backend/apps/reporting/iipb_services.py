"""Только агрегаты сопоставимых снимков ИИПБ; порог отдельно для замеров и пар."""
from collections import Counter
from statistics import mean, median

from apps.assessments.iipb import DYNAMICS_NOTICE, NOTICE, VERSION, VERSION_DATE
from apps.assessments.models import IIPBResult


def iipb_overview(tokens, bundle, threshold):
    threshold = max(5, threshold)
    measurements = list(IIPBResult.objects.filter(
        token__in=tokens, token__is_test=False, bundle=bundle, version=VERSION, version_date=VERSION_DATE,
    ))
    by_stage = {stage: {r.token_id: r for r in measurements if r.stage == stage} for stage in ("baseline", "followup")}

    def stage_block(stage):
        rows = list(by_stage[stage].values())
        if len(rows) < threshold:
            return {"participant_count": len(rows), "is_suppressed": True}
        return {
            "participant_count": len(rows), "is_suppressed": False,
            "mean": round(mean(r.index for r in rows), 2), "median": median(r.index for r in rows),
            "zone_distribution": dict(Counter(r.payload["level_label"] for r in rows)),
            "red_flag_count": sum(bool(r.payload["red_flags"]) for r in rows),
            "yellow_flag_count": sum(bool(r.payload["yellow_flags"]) for r in rows),
            "flag_distribution": dict(Counter(flag["code"] for r in rows for flag in r.payload["red_flags"] + r.payload["yellow_flags"])),
            "trait_distribution": dict(Counter(r.payload["trait_marker"]["label"] for r in rows)),
        }

    paired = by_stage["baseline"].keys() & by_stage["followup"].keys()
    trend = {"paired_count": len(paired), "is_suppressed": len(paired) < threshold}
    if len(paired) >= threshold:
        deltas = [by_stage["followup"][key].index - by_stage["baseline"][key].index for key in paired]
        trend.update({
            "mean_delta": round(mean(deltas), 2), "median_delta": median(deltas),
            "improved": sum(d > 0 for d in deltas), "worsened": sum(d < 0 for d in deltas), "stable": sum(d == 0 for d in deltas),
        })
    return {
        "version": VERSION, "version_date": VERSION_DATE, "threshold": threshold,
        "notice": NOTICE, "dynamics_notice": DYNAMICS_NOTICE,
        "baseline": stage_block("baseline"), "followup": stage_block("followup"), "trend": trend,
    }
