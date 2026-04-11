"""Promotion gate v1 — structured persistence fields (no auto-promotion)."""

from __future__ import annotations

from typing import Any

from phase38.adversarial_update import is_fatal_block


def build_promotion_gate_v1(
    *,
    hypothesis_id: str,
    pit_result: dict[str, Any],
    adversarial_updated: dict[str, Any],
) -> dict[str, Any]:
    st = str(adversarial_updated.get("phase38_resolution_status") or "")
    fatal = is_fatal_block(st)
    leakage_ok = bool((pit_result.get("leakage_audit") or {}).get("passed"))

    blocking: list[str] = []
    followups: list[str] = []

    blocking.append("hypothesis_under_test_not_eligible_for_product_promotion")
    if not leakage_ok:
        blocking.append("leakage_audit_failed")
    if fatal:
        blocking.append("adversarial_review_fatal_block")
    if st.startswith("deferred") or st == "blocked_pending_leakage_audit":
        blocking.append("adversarial_challenge_not_cleared")

    followups.append("Document governance-approved alternate PIT specs if lag/alternate joins matter.")
    followups.append("Re-run gate after Phase 39 DB runner extensions if any.")

    gate_status = "blocked"
    if not fatal and leakage_ok and st == "resolved_partial_baseline_joined":
        gate_status = "deferred_investigate_baseline_divergence"

    return {
        "hypothesis_id": hypothesis_id,
        "gate_status": gate_status,
        "blocking_reasons": blocking,
        "required_followups": followups,
        "reviewer_dependencies": [
            str(adversarial_updated.get("review_id") or "adversarial_review_v1"),
        ],
        "promotion_decision_notes": (
            "No promotion in Phase 38. Gate records explicit blockers; "
            "joined recipe / product surfaces must not treat this hypothesis as cleared."
        ),
        "phase38_context": {
            "experiment_id": pit_result.get("experiment_id"),
            "adversarial_resolution_status": st,
        },
    }
