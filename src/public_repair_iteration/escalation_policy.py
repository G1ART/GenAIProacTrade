"""Deterministic plateau detection and program-level escalation recommendation."""

from __future__ import annotations

from typing import Any

from public_repair_iteration.constants import (
    ESCALATION_RECOMMENDATIONS,
    JOINED_PLATEAU_MAX_DELTA,
    JOINED_STRONG_IMPROVEMENT_DELTA,
    MIN_MEMBERS_FOR_PREMIUM_ESCALATION,
    PREMIUM_SHARE_ESCALATION_THRESHOLD,
    THIN_HIGH_THRESHOLD,
    THIN_IMPROVEMENT_MIN_DROP,
)


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int:
    if x is None:
        return 0
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def decide_escalation_recommendation(
    snapshots: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    From ordered trend snapshots (oldest → newest), emit one of ESCALATION_RECOMMENDATIONS.

    Returns: (recommendation, rationale_dict, plateau_metrics_json, counterfactual_json)
    """
    n = len(snapshots)
    plateau_metrics: dict[str, Any] = {
        "n_iterations": n,
        "joined_series": [_i(s.get("joined_recipe_substrate_row_count")) for s in snapshots],
        "thin_series": [_f(s.get("thin_input_share")) for s in snapshots],
        "final_decisions": [str(s.get("final_decision") or "") for s in snapshots],
    }

    counterfactual: dict[str, Any] = {
        "if_more_iterations": "Collect more completed repair campaigns before premium escalation.",
        "if_substrate_jumps": "Would favor continue_public_depth.",
        "if_premium_share_drops": "Would reduce pressure toward open_targeted_premium_discovery.",
    }

    if n < 2:
        r = "hold_and_repeat_public_repair"
        rationale = {
            "rule": "insufficient_iterations",
            "n": n,
            "policy_note": "Need at least two completed snapshots for trend comparison.",
        }
        return r, rationale, plateau_metrics, counterfactual

    first = snapshots[0]
    last = snapshots[-1]
    j0 = _i(first.get("joined_recipe_substrate_row_count"))
    j1 = _i(last.get("joined_recipe_substrate_row_count"))
    t0 = _f(first.get("thin_input_share"))
    t1 = _f(last.get("thin_input_share"))
    joined_delta = j1 - j0
    thin_delta = (t1 - t0) if (t0 is not None and t1 is not None) else None

    plateau_metrics["joined_delta_first_last"] = joined_delta
    plateau_metrics["thin_delta_first_last"] = thin_delta

    prem_last = _f(last.get("premium_share_from_interp")) or 0.0
    plateau_metrics["premium_share_latest"] = prem_last

    last_decision = str(last.get("final_decision") or "")
    insuff_count = sum(
        1 for s in snapshots if str(s.get("final_decision") or "") == "repair_insufficient_repeat_buildout"
    )
    consider_prem_count = sum(
        1
        for s in snapshots
        if str(s.get("final_decision") or "") == "consider_targeted_premium_seam"
    )

    # --- open_targeted_premium_discovery (strict) ---
    if n >= MIN_MEMBERS_FOR_PREMIUM_ESCALATION:
        flat_joined = joined_delta <= JOINED_PLATEAU_MAX_DELTA
        thin_still_bad = t1 is None or t1 >= THIN_HIGH_THRESHOLD
        premium_signal = (
            prem_last >= PREMIUM_SHARE_ESCALATION_THRESHOLD
            or consider_prem_count >= 1
        )
        repeated_insuff = insuff_count >= 2 and joined_delta <= JOINED_PLATEAU_MAX_DELTA

        if flat_joined and thin_still_bad and premium_signal:
            rationale = {
                "rule": "plateau_joined_flat_thin_high_premium_signal",
                "joined_delta_first_last": joined_delta,
                "thin_latest": t1,
                "premium_share_latest": prem_last,
            }
            return (
                "open_targeted_premium_discovery",
                rationale,
                plateau_metrics,
                counterfactual,
            )

        if repeated_insuff and flat_joined:
            rationale = {
                "rule": "repeated_repair_insufficient_with_flat_substrate",
                "insufficient_runs": insuff_count,
                "joined_delta_first_last": joined_delta,
            }
            return (
                "open_targeted_premium_discovery",
                rationale,
                plateau_metrics,
                counterfactual,
            )

    # --- continue_public_depth ---
    if joined_delta >= JOINED_STRONG_IMPROVEMENT_DELTA:
        rationale = {
            "rule": "strong_joined_substrate_gain",
            "joined_delta_first_last": joined_delta,
        }
        return "continue_public_depth", rationale, plateau_metrics, counterfactual

    if thin_delta is not None and thin_delta <= -THIN_IMPROVEMENT_MIN_DROP:
        rationale = {
            "rule": "thin_input_share_materially_improved",
            "thin_delta_first_last": thin_delta,
        }
        return "continue_public_depth", rationale, plateau_metrics, counterfactual

    if last_decision == "continue_public_depth" and joined_delta > 0:
        rationale = {
            "rule": "aligned_positive_trend_with_latest_campaign_branch",
            "joined_delta_first_last": joined_delta,
        }
        return "continue_public_depth", rationale, plateau_metrics, counterfactual

    newly_rerun_ready = bool(last.get("recommend_rerun_phase16")) and not bool(
        snapshots[0].get("recommend_rerun_phase16")
    )
    if newly_rerun_ready and joined_delta >= 0:
        rationale = {"rule": "rerun_gate_newly_enabled"}
        return "continue_public_depth", rationale, plateau_metrics, counterfactual

    # --- default hold ---
    rationale = {
        "rule": "mixed_or_inconclusive",
        "joined_delta_first_last": joined_delta,
        "thin_delta_first_last": thin_delta,
    }
    return "hold_and_repeat_public_repair", rationale, plateau_metrics, counterfactual


def assert_escalation_recommendation(value: str) -> str:
    if value not in ESCALATION_RECOMMENDATIONS:
        raise ValueError(f"invalid escalation recommendation: {value}")
    return value
