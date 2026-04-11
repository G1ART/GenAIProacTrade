"""Lifecycle-aware promotion gate (Phase 39) + versioned history append."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PRIMARY_HID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"

BLOCK_INTEGRITY = "blocked_for_integrity"
BLOCK_INSUFFICIENT = "blocked_for_insufficient_evidence"
DEFERRED_COVERAGE = "deferred_pending_more_hypothesis_coverage"


def _lifecycle_map(hypotheses: list[dict[str, Any]]) -> dict[str, str]:
    return {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}


def _draft_family_count(hypotheses: list[dict[str, Any]]) -> int:
    seeds = {
        "hyp_score_publication_cadence_run_grid_lag_v1",
        "hyp_signal_availability_filing_boundary_v1",
        "hyp_issuer_sector_reporting_cadence_v1",
        "hyp_governance_safe_alternate_join_policy_v1",
    }
    n = 0
    for h in hypotheses:
        hid = str(h.get("hypothesis_id") or "")
        if hid in seeds and str(h.get("status") or "") == "draft":
            n += 1
    return n


def build_promotion_gate_phase39(
    *,
    prior_gate: dict[str, Any] | None,
    hypotheses: list[dict[str, Any]],
    adversarial_reviews: list[dict[str, Any]],
    pit_leakage_passed: bool,
    primary_adversarial_status: str,
) -> dict[str, Any]:
    life = _lifecycle_map(hypotheses)
    primary_life = life.get(PRIMARY_HID, "")
    n_draft = _draft_family_count(hypotheses)

    dep_ids: list[str] = []
    primary_review_ids: list[str] = []
    for r in adversarial_reviews:
        if str(r.get("hypothesis_id") or "") != PRIMARY_HID:
            continue
        rid = str(r.get("review_id") or "")
        if rid and rid not in primary_review_ids:
            primary_review_ids.append(rid)
        for x in r.get("resolution_dependency_review_ids") or []:
            if x and str(x) not in dep_ids:
                dep_ids.append(str(x))

    if not pit_leakage_passed or primary_adversarial_status == "blocked_pending_leakage_audit":
        category = BLOCK_INTEGRITY
        gate_status = "blocked"
        blocking = ["leakage_or_integrity_failure", "hypothesis_not_cleared_for_product"]
    elif primary_life == "challenged" and n_draft >= 3:
        category = DEFERRED_COVERAGE
        gate_status = "deferred"
        blocking = [
            "awaiting_additional_hypothesis_family_pit_binding",
            "primary_hypothesis_challenged_pending_coverage",
        ]
    else:
        category = BLOCK_INSUFFICIENT
        gate_status = "blocked"
        blocking = [
            "hypothesis_lifecycle_not_promotable",
            "adversarial_reviews_outstanding",
            "insufficient_evidence_for_product_promotion",
        ]

    gate = {
        "schema_version": 2,
        "hypothesis_id": PRIMARY_HID,
        "gate_status": gate_status,
        "primary_block_category": category,
        "lifecycle_snapshot": life,
        "blocking_reasons": blocking,
        "reviewer_dependencies": dep_ids or primary_review_ids,
        "required_followups": [
            "Implement planned PIT spec keys per pit_family_contract.family_bindings.",
            "Re-evaluate gate after at least one additional family executes under shared leakage audit.",
        ],
        "promotion_decision_notes": (
            "Phase 39: gate discriminates integrity vs insufficient evidence vs deferred pending hypothesis coverage. "
            "No auto-promotion."
        ),
        "phase39_context": {
            "draft_hypothesis_family_count": n_draft,
            "primary_hypothesis_status": primary_life,
            "pit_leakage_passed": pit_leakage_passed,
            "primary_phase38_adversarial_status": primary_adversarial_status,
        },
        "prior_gate_digest": {
            "had_phase38_context": bool((prior_gate or {}).get("phase38_context")),
        },
    }
    return gate


def append_gate_history(
    history_path: str,
    *,
    prior_record: dict[str, Any] | None,
    new_record: dict[str, Any],
) -> list[dict[str, Any]]:
    import json
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
            "phase": "phase39",
            "prior_gate_status": (prior_record or {}).get("gate_status"),
            "prior_primary_block_category": (prior_record or {}).get("primary_block_category"),
            "new_gate": new_record,
        }
    )
    write_json(p, hist)
    return hist
