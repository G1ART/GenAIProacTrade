"""Deterministic survival / demotion policy (Phase 15)."""

from __future__ import annotations

from typing import Any

from research_validation.constants import (
    BEAT_BASELINE_EPS,
    CONTRADICTION_FAIL_THRESHOLD,
    NAIVE_NULL_SPREAD,
    STABILITY_WEAK_THRESHOLD,
)

_STATUS_RANK = {
    "archive_failed": 0,
    "demote_to_sandbox": 1,
    "weak_survival": 2,
    "survives": 3,
}
_RANK_STATUS = {v: k for k, v in _STATUS_RANK.items()}


def _narrow_ceiling(current: str, ceiling: str) -> str:
    return _RANK_STATUS[min(_STATUS_RANK[current], _STATUS_RANK[ceiling])]


def _cap_to_max_clean(status: str, max_clean: str) -> str:
    return _RANK_STATUS[min(_STATUS_RANK[status], _STATUS_RANK[max_clean])]


def decide_survival(
    *,
    hypothesis_status: str,
    program_quality_class: str,
    recipe_spread_pooled: float | None,
    sc_spread_pooled: float | None,
    mcap_spread_pooled: float | None,
    beats_state_change: bool,
    beats_naive: bool,
    beats_size: bool,
    window_stability_ratio: float,
    contradiction_residual_count: int,
    thin_input_heavy: bool,
    failed_degraded_emphasis: bool,
) -> dict[str, Any]:
    max_clean = "survives"
    if hypothesis_status == "sandboxed":
        max_clean = _narrow_ceiling(max_clean, "weak_survival")
    if program_quality_class == "thin_input" or thin_input_heavy:
        max_clean = _narrow_ceiling(max_clean, "weak_survival")
    if failed_degraded_emphasis:
        max_clean = _narrow_ceiling(max_clean, "demote_to_sandbox")

    rationale_parts: list[str] = []
    fragility: dict[str, Any] = {
        "window_stability_ratio": window_stability_ratio,
        "contradiction_residual_count": contradiction_residual_count,
        "program_quality_class": program_quality_class,
        "hypothesis_status_at_validation": hypothesis_status,
        "max_clean_applied": max_clean,
    }

    if recipe_spread_pooled is None or sc_spread_pooled is None:
        rationale_parts.append("insufficient_sample_for_spreads")
        status = "archive_failed"
        next_step = {"action": "archive_or_reforge_hypothesis"}
    else:
        loses_core = recipe_spread_pooled + BEAT_BASELINE_EPS < sc_spread_pooled
        loses_all = not beats_state_change and not beats_naive and not beats_size

        if (
            contradiction_residual_count >= CONTRADICTION_FAIL_THRESHOLD
            and loses_core
        ):
            rationale_parts.append(
                "residual_contradictions_and_loses_state_change_baseline"
            )
            status = "archive_failed"
            next_step = {"action": "document_contradictions"}
        elif loses_all or recipe_spread_pooled <= NAIVE_NULL_SPREAD + BEAT_BASELINE_EPS / 2:
            rationale_parts.append("no_uplift_vs_explicit_baselines")
            status = "archive_failed"
            next_step = {"action": "archive_failed_recipe"}
        elif loses_core:
            rationale_parts.append("does_not_beat_state_change_baseline")
            if hypothesis_status == "sandboxed":
                status = "demote_to_sandbox"
                next_step = {"action": "keep_sandbox_rework_features"}
            else:
                status = "weak_survival"
                next_step = {"action": "optional_refinement"}
        elif window_stability_ratio < STABILITY_WEAK_THRESHOLD:
            rationale_parts.append("fragile_across_windows")
            status = "weak_survival"
            next_step = {"action": "monitor_stability"}
        elif (
            mcap_spread_pooled is not None
            and recipe_spread_pooled + BEAT_BASELINE_EPS < mcap_spread_pooled
        ):
            rationale_parts.append("size_baseline_competitive_or_stronger")
            status = "weak_survival"
            next_step = {"action": "control_for_size_illusion"}
        else:
            rationale_parts.append("beats_explicit_baselines_stable_windows")
            status = "survives"
            next_step = {"action": "keep_candidate_recipe_monitor"}

    rationale = "; ".join(rationale_parts) if rationale_parts else "policy_result"
    before_cap = status
    status = _cap_to_max_clean(status, max_clean)
    if status != before_cap:
        rationale = f"{rationale}; enforced_cap={max_clean}"

    return {
        "survival_status": status,
        "rationale": rationale,
        "fragility_json": fragility,
        "next_step_json": next_step,
    }
