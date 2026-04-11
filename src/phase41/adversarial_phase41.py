"""Append-only family reviews after Phase 41 falsifier substrate run."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from phase37.adversarial_review import CritiqueCategory, DecisionImpact, ReviewerStance

BATCH_TAG = "phase41_falsifier_substrate_review"


def phase41_substrate_reviews(
    *,
    pit_result: dict[str, Any],
    transitioned_utc: str | None = None,
) -> list[dict[str, Any]]:
    ts = transitioned_utc or datetime.now(timezone.utc).isoformat()
    filing_s = (pit_result.get("filing_substrate") or {}).get("summary") or {}
    sector_s = (pit_result.get("sector_substrate") or {}).get("summary") or {}
    proxy_n = int(filing_s.get("rows_with_explicit_signal_proxy") or 0)
    row_n = int(filing_s.get("row_count") or 0)
    sec_miss = int((sector_s.get("by_classification") or {}).get("sector_metadata_missing") or 0)

    filing_text = (
        f"Phase 41 filing substrate: {row_n} rows, {proxy_n} still on explicit signal_available_date proxy; "
        "see bundle filing_substrate.per_row for exact vs filed-date vs unavailable classifications."
    )
    sector_text = (
        f"Phase 41 sector substrate: {sec_miss}/{sector_s.get('row_count', 0)} rows missing sector metadata; "
        "sector_stratified_signal_pick_v1 uses market_metadata_latest.sector when present else stratum unknown."
    )

    templates: list[tuple[str, str, str, str]] = [
        (
            "hyp_signal_availability_filing_boundary_v1",
            filing_text,
            CritiqueCategory.DATA.value,
            DecisionImpact.REQUIRE_EXTRA_TEST.value,
            "signal_filing_boundary_v1",
        ),
        (
            "hyp_issuer_sector_reporting_cadence_v1",
            sector_text,
            CritiqueCategory.MECHANISM.value,
            DecisionImpact.REQUIRE_EXTRA_TEST.value,
            "issuer_sector_reporting_cadence_v1",
        ),
    ]
    out: list[dict[str, Any]] = []
    for hid, text, cat, impact, fid in templates:
        out.append(
            {
                "review_id": str(uuid4()),
                "hypothesis_id": hid,
                "reviewer_stance": ReviewerStance.DATA_LINEAGE_AUDITOR.value,
                "critique_category": cat,
                "challenge_text": text,
                "decision_impact": impact,
                "resolution": "deferred",
                "resolution_notes": "Phase 41 falsifier substrate batch; queryable via phase41_family_id.",
                "created_utc": ts,
                BATCH_TAG: True,
                "phase41_family_id": fid,
                "explicit_impact": "substrate_governance_record",
            }
        )
    return out


def merge_phase41_adversarial(
    existing: list[dict[str, Any]],
    new_batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append Phase 41 reviews each run (append-only; distinct review_id)."""
    return list(existing) + list(new_batch)
