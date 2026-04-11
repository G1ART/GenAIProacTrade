"""Phase 43 recommendation after Phase 42 evidence accumulation."""

from __future__ import annotations

from typing import Any


def recommend_phase43_after_phase42(*, bundle: dict[str, Any]) -> dict[str, Any]:
    gate = bundle.get("promotion_gate_phase42") or {}
    cat = str(gate.get("primary_block_category") or "")
    if "non_discriminating" in cat:
        rec = "add_bounded_cohort_b_or_tighten_specs_for_discrimination_v1"
        why = (
            "Outcome rollups across rerun families still overlap; next step is a capped secondary cohort "
            "or spec tightening so families can falsify one another on counts—not broader substrate repair."
        )
    elif "proxy" in cat:
        rec = "substrate_backfill_or_narrow_claims_then_retest_v1"
        why = (
            "Proxy filing bounds or missing sector rows remain; strengthen rows (backfill) or narrow claims "
            "before expecting cleaner discrimination."
        )
    else:
        rec = "governance_review_and_operator_closeout_v1"
        why = (
            "Gate is deferred for governance / claim-scope review; document decision, link artifacts, "
            "and avoid auto-promotion."
        )
    return {"phase43_recommendation": rec, "rationale": why}
