"""Before/after survival and campaign recommendation deltas."""

from __future__ import annotations

from typing import Any


def _dist_get(dist: dict[str, Any], key: str) -> int:
    v = dist.get(key)
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def compare_survival_distributions(
    before_dist: dict[str, Any], after_dist: dict[str, Any]
) -> dict[str, Any]:
    keys = (
        "survives",
        "weak_survival",
        "demote_to_sandbox",
        "archive_failed",
    )
    deltas: dict[str, int] = {}
    for k in keys:
        b = _dist_get(before_dist, k)
        a = _dist_get(after_dist, k)
        deltas[k] = a - b
    return {
        "deltas": deltas,
        "before": {k: _dist_get(before_dist, k) for k in keys},
        "after": {k: _dist_get(after_dist, k) for k in keys},
        "outcome_improved_heuristic": bool(
            deltas.get("survives", 0) > 0
            or deltas.get("weak_survival", 0) < 0
            or deltas.get("archive_failed", 0) < 0
        ),
    }


def build_improvement_interpretation(
    *,
    survival_compare: dict[str, Any],
    before_rec: str | None,
    after_rec: str | None,
    after_campaign_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    total_f = int((after_campaign_metrics or {}).get("total_failure_cases_across_members") or 0)
    contra = int((after_campaign_metrics or {}).get("n_contradictory_failure_cases") or 0)
    prem = int((after_campaign_metrics or {}).get("n_failure_cases_with_nonempty_premium_hint") or 0)
    premium_signal = contra + prem
    premium_share = (premium_signal / total_f) if total_f > 0 else 0.0
    return {
        "survival_compare": survival_compare,
        "recommendation_before": before_rec,
        "recommendation_after": after_rec,
        "recommendation_changed": (before_rec or "") != (after_rec or ""),
        "after_campaign_failure_totals": {
            "total_failure_cases": total_f,
            "premium_signal_cases": premium_signal,
            "premium_share": round(premium_share, 6),
            "n_contradictory_failure_cases": contra,
        },
    }
