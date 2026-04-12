"""Machine-readable narrowed claims after Phase 43 truthfulness assessment."""

from __future__ import annotations

from typing import Any


def build_claim_narrowing(
    *,
    truth: dict[str, Any],
    retry: dict[str, Any],
    scorecard_before: dict[str, Any],
    scorecard_after: dict[str, Any],
) -> dict[str, Any]:
    material = bool(truth.get("material_falsifier_improvement"))
    filing_elig = bool(retry.get("filing_retry_eligible"))
    sector_elig = bool(retry.get("sector_retry_eligible"))

    def _filing_status() -> str:
        if filing_elig:
            return "bounded_retry_allowed"
        if material:
            return "bounded_retry_not_yet_justified"
        return "narrowed"

    def _sector_status() -> str:
        if sector_elig:
            return "bounded_retry_allowed"
        if material:
            return "bounded_retry_not_yet_justified"
        return "narrowed"

    fb = scorecard_before.get("filing_blocker_distribution") or {}
    fa = scorecard_after.get("filing_blocker_distribution") or {}
    sb = scorecard_before.get("sector_blocker_distribution") or {}
    sa = scorecard_after.get("sector_blocker_distribution") or {}

    family_claim_limits = {
        "signal_filing_boundary_v1": {
            "claim_status": _filing_status(),
            "supported_scope": (
                "Cohort-level statement that pre-signal filing-public strict pick remains proxy- or "
                "blocker-limited for the Phase 43 8-row fixture; bounded ingest did not increase "
                "exact_public_ts_available or filed-date-only usability in scorecard aggregates."
            ),
            "unsupported_scope": (
                "Claims that filing-public falsifier quality materially improved for this cohort "
                "without exact_public_ts_available or accepted_at_missing_but_filed_date_only gains."
            ),
            "reason": (
                f"Filing distributions before/after: {fb!r} → {fa!r}. "
                "No aggregate filing falsifier upgrade; retry only with a newly named ingestion path."
            ),
        },
        "issuer_sector_reporting_cadence_v1": {
            "claim_status": _sector_status(),
            "supported_scope": (
                "Sector diagnosis refined: metadata row exists but sector field remains blank for all "
                "8 rows; sector-informed stratification is still unavailable."
            ),
            "unsupported_scope": (
                "Sector-based falsification or sector_available-backed claims for this cohort "
                "without a new provider/path that populates sector."
            ),
            "reason": (
                f"Sector distributions before/after: {sb!r} → {sa!r}. "
                "no_market_metadata_row → sector_field_blank is taxonomy precision only unless "
                "sector_available increases."
            ),
        },
    }

    cohort_status = "bounded_retry_allowed" if (filing_elig or sector_elig) else "narrowed"
    if cohort_status == "narrowed" and material:
        cohort_status = "bounded_retry_not_yet_justified"

    cohort_claim_limits = {
        "claim_status": cohort_status,
        "supported_scope": (
            "Proxy-limited falsifier substrate remains for this bounded cohort; broad public-core "
            "reopening is not justified by Phase 43 evidence."
        ),
        "unsupported_scope": (
            "Broad filing_index campaigns, broad metadata campaigns, or auto-promotion from Phase 43 alone."
        ),
        "reason": (
            "Phase 44 assessment: "
            + ("material substrate signal present but no new named retry path; " if material else "")
            + "see per-family limits and retry_eligibility."
        ),
    }

    bounded_retry_eligibility = (
        "eligible_on_declared_new_source"
        if (filing_elig or sector_elig)
        else "not_eligible_without_named_new_path"
    )

    return {
        "family_claim_limits": family_claim_limits,
        "cohort_claim_limits": cohort_claim_limits,
        "bounded_retry_eligibility": bounded_retry_eligibility,
    }
