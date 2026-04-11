"""Promotion gate after Phase 42 evidence accumulation (schema v4 extended context)."""

from __future__ import annotations

from typing import Any

PRIMARY_HID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"

BLOCK_INTEGRITY = "blocked_for_integrity"
DEFERRED_PROXY = "deferred_due_to_proxy_limited_falsifier_substrate"
DEFERRED_NON_DISC = "deferred_due_to_non_discriminating_evidence"
DEFERRED_BROAD = "deferred_due_to_claim_scope_too_broad"


def build_promotion_gate_phase42(
    *,
    prior_gate: dict[str, Any] | None,
    phase41_pit: dict[str, Any],
    scorecard: dict[str, Any],
    discrimination_summary: dict[str, Any],
    narrowing: dict[str, Any],
    hypotheses: list[dict[str, Any]],
) -> dict[str, Any]:
    life = {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}
    all_leak = bool(phase41_pit.get("all_families_leakage_passed"))

    n = int(scorecard.get("cohort_row_count") or 0)
    fd = scorecard.get("filing_blocker_distribution") or {}
    sd = scorecard.get("sector_blocker_distribution") or {}
    filing_strong = int(fd.get("exact_public_ts_available", 0)) + int(
        fd.get("accepted_at_missing_but_filed_date_only", 0)
    )
    sector_ok = int(sd.get("sector_available", 0))
    filing_proxy = max(n - filing_strong, 0)
    sector_miss = max(n - sector_ok, 0)

    any_disc = bool(discrimination_summary.get("any_family_outcome_discriminating"))
    narrow_headline = str((narrowing or {}).get("headline") or "")

    if not all_leak:
        category = BLOCK_INTEGRITY
        gate_status = "blocked"
        blocking = ["leakage_audit_failed_phase41_reference", "integrity_block"]
    elif filing_proxy > 0 or sector_miss > 0:
        category = DEFERRED_PROXY
        gate_status = "deferred"
        blocking = []
        if filing_proxy > 0:
            blocking.append("filing_proxy_or_blocker_rows_remain")
        if sector_miss > 0:
            blocking.append("sector_metadata_missing_rows_remain")
        blocking.append("await_stronger_falsifier_substrate")
    elif not any_disc and "no_outcome_discrimination" in narrow_headline:
        category = DEFERRED_NON_DISC
        gate_status = "deferred"
        blocking = [
            "rerun_families_identical_outcome_rollups",
            "evidence_accumulation_did_not_add_discrimination",
        ]
    else:
        category = DEFERRED_BROAD
        gate_status = "deferred"
        blocking = ["claim_scope_or_governance_review_needed", "no_auto_promotion"]

    return {
        "schema_version": 4,
        "phase": "phase42",
        "hypothesis_id": PRIMARY_HID,
        "gate_status": gate_status,
        "primary_block_category": category,
        "lifecycle_snapshot": life,
        "blocking_reasons": blocking,
        "reviewer_dependencies": [],
        "required_followups": [
            "Track scorecard deltas across runs using stable_run_digest.",
            "Narrow claims where proxy_limited_retest_needed; add cohort B only with tight cap.",
        ],
        "promotion_decision_notes": (
            "Phase 42: evidence accumulation + blocker taxonomy + discrimination summary. No auto-promotion."
        ),
        "phase42_context": {
            "all_families_leakage_passed_phase41": all_leak,
            "filing_proxy_row_count": filing_proxy,
            "sector_missing_row_count": sector_miss,
            "any_family_outcome_discriminating": any_disc,
            "narrowing_headline": narrow_headline,
        },
        "prior_gate_digest": {
            "had_schema_version": (prior_gate or {}).get("schema_version"),
            "prior_primary_block_category": (prior_gate or {}).get("primary_block_category"),
            "prior_phase": (prior_gate or {}).get("phase"),
        },
    }


def append_gate_history_phase42(
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
            "phase": "phase42",
            "prior_gate_status": (prior_record or {}).get("gate_status"),
            "prior_primary_block_category": (prior_record or {}).get("primary_block_category"),
            "new_gate": new_record,
        }
    )
    write_json(p, hist)
    return hist
