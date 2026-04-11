"""Deterministic hypothesis / family narrowing labels (no auto-promotion)."""

from __future__ import annotations

from typing import Any

_FAMILY_TO_HYP = {
    "signal_filing_boundary_v1": "hyp_signal_availability_filing_boundary_v1",
    "issuer_sector_reporting_cadence_v1": "hyp_issuer_sector_reporting_cadence_v1",
}


def narrow_families_for_phase42(
    *,
    families_executed: list[dict[str, Any]],
    discrimination_summary: dict[str, Any],
    row_level_blockers: list[dict[str, Any]],
    evidence_density: dict[str, Any],
) -> dict[str, Any]:
    """
    Assign narrowing_status per Phase 41-rerun family.
    """
    disc_ids = set(discrimination_summary.get("live_and_discriminating_family_ids") or [])
    any_disc = bool(discrimination_summary.get("any_family_outcome_discriminating"))

    # Proxy pressure: filing not exact ts for all rows; sector not available for all
    filing_weak = any(
        r.get("filing_blocker_cause") not in ("exact_public_ts_available",)
        and r.get("filing_blocker_cause")
        != "accepted_at_missing_but_filed_date_only"
        for r in row_level_blockers
    )
    sector_weak = any(r.get("sector_blocker_cause") != "sector_available" for r in row_level_blockers)

    by_family: dict[str, dict[str, Any]] = {}
    for f in families_executed:
        fid = str(f.get("family_id") or "")
        if fid not in _FAMILY_TO_HYP:
            continue

        proxy = filing_weak if fid == "signal_filing_boundary_v1" else sector_weak

        if fid in disc_ids:
            status = "live_and_discriminating"
        elif proxy:
            status = "proxy_limited_retest_needed"
        else:
            status = "still_live_but_non_discriminating"

        claim = "narrow_claim_required" if fid not in disc_ids else None

        by_family[fid] = {
            "hypothesis_id": _FAMILY_TO_HYP[fid],
            "narrowing_status": status,
            "proxy_limited_substrate": bool(proxy),
            "suggested_claim_adjustment": claim,
        }

    return {
        "by_family_id": by_family,
        "headline": (
            "no_outcome_discrimination_across_rerun_families"
            if not any_disc
            else "at_least_one_family_outcome_discriminating"
        ),
    }
