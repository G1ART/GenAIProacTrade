"""Phase 39 recommendation from Phase 38 PIT evidence."""

from __future__ import annotations

from typing import Any


def recommend_phase39_after_phase38(*, pit_result: dict[str, Any]) -> dict[str, Any]:
    rows = pit_result.get("row_results") or []
    leakage_ok = bool((pit_result.get("leakage_audit") or {}).get("passed"))

    def any_cat(spec: str, cat: str) -> bool:
        k = (
            "baseline"
            if spec == "baseline"
            else "lag_signal_bound"
            if spec == "lag"
            else "alternate_prior_run"
        )
        return any(
            str((r.get(k) or {}).get("outcome_category") or "") == cat for r in rows
        )

    joined_lag = any_cat("lag", "reclassified_to_joined")
    joined_alt = any_cat("alternate", "reclassified_to_joined")
    joined_base = any_cat("baseline", "reclassified_to_joined")

    if not leakage_ok:
        return {
            "phase39_recommendation": "remediate_pit_join_leakage_and_replay_phase38",
            "rationale": "Leakage audit failed; fix pick/bound logic before expanding hypothesis or UX work.",
        }
    if joined_base:
        return {
            "phase39_recommendation": "reconcile_fixture_baseline_divergence_with_substrate_audit",
            "rationale": "Baseline PIT joined some fixture rows; trace run_id / score grid drift vs Phase 36.1 audit.",
        }
    if joined_lag or joined_alt:
        return {
            "phase39_recommendation": "encode_governance_safe_alternate_specs_and_promotion_criteria",
            "rationale": (
                "Alternate or lag spec produced joined outcomes; formalize which spec is product-relevant "
                "and update promotion gate + explanation contracts."
            ),
        }
    return {
        "phase39_recommendation": "broaden_hypothesis_families_and_harden_explanation_under_persistent_mismatch",
        "rationale": (
            "Fixture remains join_key_mismatch under executed specs; expand research hypotheses beyond "
            "this single seam and strengthen user-facing explanation of persistent PIT boundaries."
        ),
    }
