"""Bounded retry requires a named new source/path beyond Phase 43's declared actions."""

from __future__ import annotations

from typing import Any


def _paths_used_from_phase43(phase43_bundle: dict[str, Any]) -> dict[str, str]:
    bf = (phase43_bundle.get("backfill_actions") or {}).get("filing") or {}
    bs = (phase43_bundle.get("backfill_actions") or {}).get("sector") or {}
    return {
        "filing": str(bf.get("repair") or "unknown"),
        "sector": str(bs.get("provider") or bs.get("status") or "unknown"),
    }


def build_retry_eligibility(
    *,
    phase43_bundle: dict[str, Any],
    material_falsifier_improvement: bool,
    declared_new_filing_source: str | None = None,
    declared_new_sector_source: str | None = None,
) -> dict[str, Any]:
    """
    Without an operator-declared *new* path, filing/sector retry stays ineligible even if
    Phase 43 left residual blockers (prevents generic "try again" loops).
    """
    used = _paths_used_from_phase43(phase43_bundle)
    new_f = (declared_new_filing_source or "").strip()
    new_s = (declared_new_sector_source or "").strip()

    filing_ok = bool(new_f) and new_f.lower() not in (
        used["filing"].lower(),
        "none",
        "n/a",
    )
    sector_ok = bool(new_s) and new_s.lower() not in (
        used["sector"].lower(),
        "none",
        "n/a",
    )

    filing_retry_eligible = bool(filing_ok and material_falsifier_improvement)
    sector_retry_eligible = bool(sector_ok and material_falsifier_improvement)

    reasons: list[str] = []
    if not new_f:
        reasons.append(
            "No named alternative filing ingestion path declared; cannot authorize another bounded filing pass."
        )
    if not new_s:
        reasons.append(
            "No named alternative sector fill path declared; cannot authorize another bounded sector pass."
        )
    if not material_falsifier_improvement:
        reasons.append(
            "Phase 44 truthfulness: no material falsifier usability / gate / discrimination improvement."
        )

    return {
        "filing_retry_eligible": filing_retry_eligible,
        "sector_retry_eligible": sector_retry_eligible,
        "eligibility_reason": " ".join(reasons) if reasons else "declared_new_sources_present_and_material_gain",
        "required_new_source_or_path": {
            "filing": new_f or "operator_must_name_concrete_alternative_to_phase43_filing_repair",
            "sector": new_s or "operator_must_name_concrete_provider_path_that_emits_nonempty_sector",
        },
        "phase43_paths_already_used": used,
        "material_falsifier_improvement_required": True,
        "material_falsifier_improvement_observed": material_falsifier_improvement,
    }
