"""Promotion gate schema v4 after Phase 41 falsifier substrate."""

from __future__ import annotations

from typing import Any

PRIMARY_HID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"

BLOCK_INTEGRITY = "blocked_for_integrity"
COND_NOT_PROMOTABLE = "conditionally_supported_but_not_promotable"
DEFERRED_PROXY_SUBSTRATE = "deferred_due_to_proxy_limited_falsifier_substrate"


def build_promotion_gate_phase41(
    *,
    prior_gate: dict[str, Any] | None,
    pit_result: dict[str, Any],
    hypotheses: list[dict[str, Any]],
) -> dict[str, Any]:
    life = {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}
    all_leak = bool(pit_result.get("all_families_leakage_passed"))
    families = pit_result.get("families_executed") or []
    any_joined = any(bool(f.get("joined_any_row")) for f in families)

    filing_s = (pit_result.get("filing_substrate") or {}).get("summary") or {}
    sector_s = (pit_result.get("sector_substrate") or {}).get("summary") or {}
    row_n = int(filing_s.get("row_count") or 0)
    proxy_n = int(filing_s.get("rows_with_explicit_signal_proxy") or 0)
    sec_by_c = sector_s.get("by_classification") or {}
    sec_miss = int(sec_by_c.get("sector_metadata_missing") or 0)
    sec_n = int(sector_s.get("row_count") or 0)

    still_proxy = row_n > 0 and proxy_n > 0
    still_sector_gap = sec_n > 0 and sec_miss > 0

    if not all_leak:
        category = BLOCK_INTEGRITY
        gate_status = "blocked"
        blocking = ["leakage_audit_failed_phase41_family", "hypothesis_not_cleared_for_product"]
    elif any_joined:
        category = COND_NOT_PROMOTABLE
        gate_status = "deferred"
        blocking = ["joined_outcomes_under_research_specs", "no_auto_promotion"]
    elif still_proxy or still_sector_gap:
        category = DEFERRED_PROXY_SUBSTRATE
        gate_status = "deferred"
        blocking = []
        if still_proxy:
            blocking.append("filing_timestamp_still_proxy_for_one_or_more_rows")
        if still_sector_gap:
            blocking.append("sector_metadata_missing_for_one_or_more_rows")
        blocking.append("await_stronger_falsifier_substrate_or_narrower_claims")
    else:
        category = COND_NOT_PROMOTABLE
        gate_status = "deferred"
        blocking = [
            "falsifier_substrate_improved_but_primary_hypothesis_unchanged",
            "no_auto_promotion",
            "evidence_accumulation_next",
        ]

    return {
        "schema_version": 4,
        "phase": "phase41",
        "hypothesis_id": PRIMARY_HID,
        "gate_status": gate_status,
        "primary_block_category": category,
        "lifecycle_snapshot": life,
        "blocking_reasons": blocking,
        "reviewer_dependencies": [],
        "required_followups": [
            "Accumulate evidence under stronger falsifiers or narrow competing hypotheses.",
            "Tighten explanation / governance if mismatch persists.",
        ],
        "promotion_decision_notes": (
            "Phase 41: filing_index + market_metadata substrate for two families; no auto-promotion."
        ),
        "phase41_context": {
            "filing_proxy_row_count": proxy_n,
            "filing_row_count": row_n,
            "sector_missing_row_count": sec_miss,
            "sector_row_count": sec_n,
            "all_families_leakage_passed": all_leak,
        },
        "prior_gate_digest": {
            "had_schema_version": (prior_gate or {}).get("schema_version"),
            "prior_primary_block_category": (prior_gate or {}).get("primary_block_category"),
        },
    }


def append_gate_history_phase41(
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
            "phase": "phase41",
            "prior_gate_status": (prior_record or {}).get("gate_status"),
            "prior_primary_block_category": (prior_record or {}).get("primary_block_category"),
            "new_gate": new_record,
        }
    )
    write_json(p, hist)
    return hist
