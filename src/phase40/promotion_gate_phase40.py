"""Promotion gate after Phase 40 — extended primary_block_category."""

from __future__ import annotations

from typing import Any

PRIMARY_HID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"

BLOCK_INTEGRITY = "blocked_for_integrity"
BLOCK_INSUFFICIENT = "blocked_for_insufficient_evidence"
DEFERRED_COVERAGE = "deferred_pending_more_hypothesis_coverage"
COND_NOT_PROMOTABLE = "conditionally_supported_but_not_promotable"


def _lifecycle_map(hypotheses: list[dict[str, Any]]) -> dict[str, str]:
    return {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}


def build_promotion_gate_phase40(
    *,
    prior_gate: dict[str, Any] | None,
    pit_result: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    adversarial_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    life = _lifecycle_map(hypotheses)
    all_leak = bool(pit_result.get("all_families_leakage_passed"))
    families = pit_result.get("families_executed") or []
    any_joined = any(bool(f.get("joined_any_row")) for f in families)
    n_families = len(families)
    n_cond = sum(1 for h in hypotheses if str(h.get("status") or "") == "conditionally_supported")

    dep_ids = list(
        dict.fromkeys(
            str(r.get("review_id"))
            for r in adversarial_reviews
            if str(r.get("hypothesis_id") or "") == PRIMARY_HID
            and str(r.get("review_id") or "")
        )
    )

    if not all_leak:
        category = BLOCK_INTEGRITY
        gate_status = "blocked"
        blocking = ["leakage_audit_failed_in_one_or_more_families", "hypothesis_not_cleared_for_product"]
    elif any_joined:
        category = COND_NOT_PROMOTABLE
        gate_status = "deferred"
        blocking = [
            "joined_outcomes_observed_under_research_specs",
            "no_auto_promotion_pending_governance_review",
        ]
    elif n_cond >= 4 and n_families >= 5:
        category = COND_NOT_PROMOTABLE
        gate_status = "deferred"
        blocking = [
            "families_executed_under_shared_audit",
            "evidence_accumulated_without_product_clearance",
            "primary_hypothesis_remains_challenged",
        ]
    elif n_families < 5:
        category = DEFERRED_COVERAGE
        gate_status = "deferred"
        blocking = ["incomplete_family_execution", "awaiting_full_pit_family_matrix"]
    else:
        category = BLOCK_INSUFFICIENT
        gate_status = "blocked"
        blocking = ["adversarial_reviews_outstanding", "insufficient_evidence_for_product_promotion"]

    return {
        "schema_version": 3,
        "phase": "phase40",
        "hypothesis_id": PRIMARY_HID,
        "gate_status": gate_status,
        "primary_block_category": category,
        "lifecycle_snapshot": life,
        "blocking_reasons": blocking,
        "reviewer_dependencies": dep_ids[:12],
        "required_followups": [
            "Wire filing timestamps or sector metadata if filing/sector hypotheses should falsify.",
            "Re-run gate after Phase 41 substrate or narrative tightening.",
        ],
        "promotion_decision_notes": (
            "Phase 40: family-specific PIT execution under shared leakage rule. No auto-promotion."
        ),
        "phase40_context": {
            "families_executed_count": n_families,
            "implemented_family_spec_count": pit_result.get("implemented_family_spec_count"),
            "all_families_leakage_passed": all_leak,
            "any_family_joined_row": any_joined,
            "conditionally_supported_hypothesis_count": n_cond,
        },
        "prior_gate_digest": {
            "had_schema_version": (prior_gate or {}).get("schema_version"),
            "prior_primary_block_category": (prior_gate or {}).get("primary_block_category"),
        },
    }


def append_gate_history_phase40(
    history_path: str,
    *,
    prior_record: dict[str, Any] | None,
    new_record: dict[str, Any],
) -> list[dict[str, Any]]:
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    from phase37.persistence import ensure_research_data_dir, write_json

    p = Path(history_path)
    ensure_research_data_dir(p.parent)
    hist: list[dict[str, Any]] = []
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                hist = raw
        except (OSError, json.JSONDecodeError):
            hist = []
    hist.append(
        {
            "decision_utc": datetime.now(timezone.utc).isoformat(),
            "phase": "phase40",
            "prior_gate_status": (prior_record or {}).get("gate_status"),
            "prior_primary_block_category": (prior_record or {}).get("primary_block_category"),
            "new_gate": new_record,
        }
    )
    write_json(p, hist)
    return hist
