"""Deterministic final branch after repair + optional revalidation."""

from __future__ import annotations

from typing import Any

from public_repair_campaign.constants import (
    FINAL_DECISIONS,
    MIN_CONTRADICTORY_FOR_PREMIUM_BRANCH,
    PREMIUM_SHARE_GATE,
    REPAIR_CAMPAIGN_POLICY_VERSION,
)


def substrate_improved_from_buildout(improvement: dict[str, Any] | None) -> bool:
    if not improvement:
        return False
    su = improvement.get("substrate_uplift") or {}
    if su.get("joined_substrate_improved"):
        return True
    if su.get("thin_input_improved") is True:
        return True
    tracked = (improvement.get("exclusion_improvement") or {}).get("tracked") or {}
    for _k, row in tracked.items():
        if isinstance(row, dict) and row.get("reduced"):
            return True
    return False


def premium_evidence_from_campaign_metrics(metrics: dict[str, Any] | None) -> bool:
    if not metrics:
        return False
    total_f = int(metrics.get("total_failure_cases_across_members") or 0)
    if total_f <= 0:
        return False
    contra = int(metrics.get("n_contradictory_failure_cases") or 0)
    prem = int(metrics.get("n_failure_cases_with_nonempty_premium_hint") or 0)
    signal = contra + prem
    share = signal / total_f
    return share >= PREMIUM_SHARE_GATE and contra >= MIN_CONTRADICTORY_FOR_PREMIUM_BRANCH


def decide_final_repair_branch(
    *,
    substrate_improved: bool,
    reruns_executed: bool,
    improvement_summary: dict[str, Any] | None,
    survival_compare: dict[str, Any],
    before_campaign_recommendation: str | None,
    after_campaign_recommendation: str | None,
    after_campaign_metrics: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """
    Exactly one of FINAL_DECISIONS.

    Invariant: ``consider_targeted_premium_seam`` requires ``reruns_executed`` and
    substrate repair — premium seam is never chosen only because reruns were skipped.
    """
    rationale: dict[str, Any] = {
        "policy_version": REPAIR_CAMPAIGN_POLICY_VERSION,
        "substrate_improved": substrate_improved,
        "reruns_executed": reruns_executed,
        "after_campaign_recommendation": after_campaign_recommendation,
        "before_campaign_recommendation": before_campaign_recommendation,
    }

    if not reruns_executed:
        rationale["rule"] = "no_post_repair_rerun_evidence"
        return "repair_insufficient_repeat_buildout", rationale

    if not substrate_improved:
        rationale["rule"] = "substrate_not_improved_after_buildout"
        return "repair_insufficient_repeat_buildout", rationale

    if after_campaign_recommendation == "targeted_premium_seam_first":
        rationale["rule"] = "phase16_recommendation_premium_seam"
        return "consider_targeted_premium_seam", rationale

    if premium_evidence_from_campaign_metrics(after_campaign_metrics):
        rationale["rule"] = "premium_signal_share_after_rerun"
        return "consider_targeted_premium_seam", rationale

    sc = survival_compare.get("deltas") or {}
    if survival_compare.get("outcome_improved_heuristic"):
        rationale["rule"] = "survival_outcomes_improved"
        rationale["deltas"] = sc
        return "continue_public_depth", rationale

    if after_campaign_recommendation == "public_data_depth_first":
        rationale["rule"] = "plateau_public_depth_still_indicated"
        rationale["deltas"] = sc
        return "continue_public_depth", rationale

    if after_campaign_recommendation == "insufficient_evidence_repeat_campaign":
        rationale["rule"] = "insufficient_evidence_after_rerun"
        rationale["deltas"] = sc
        return "repair_insufficient_repeat_buildout", rationale

    rationale["rule"] = "default_more_public_repair"
    rationale["deltas"] = sc
    return "repair_insufficient_repeat_buildout", rationale


def assert_final_decision(value: str) -> str:
    if value not in FINAL_DECISIONS:
        raise ValueError(f"invalid repair campaign final decision: {value}")
    return value
