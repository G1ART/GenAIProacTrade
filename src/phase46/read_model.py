"""Canonical founder-facing read model from Phase 45 + Phase 44 bundles (no raw dump)."""

from __future__ import annotations

from typing import Any


def build_founder_read_model(
    *,
    phase45_bundle: dict[str, Any],
    phase44_bundle: dict[str, Any],
    input_phase45_bundle_path: str,
    input_phase44_bundle_path: str,
) -> dict[str, Any]:
    ar = phase45_bundle.get("authoritative_resolution") or {}
    cc = phase45_bundle.get("canonical_closeout") or {}
    st = phase45_bundle.get("current_closeout_status") or {}
    fr = phase45_bundle.get("future_reopen_protocol") or {}
    p46 = phase45_bundle.get("phase46") or {}
    truth = phase44_bundle.get("phase44_truthfulness_assessment") or {}
    gate = phase44_bundle.get("gate_after") or {}

    cohort = cc.get("cohort") or {}
    rows = cohort.get("rows") or []

    what_changed = [x.get("detail") or str(x) for x in (cc.get("what_changed") or [])]
    what_did_not = [x.get("detail") or str(x) for x in (cc.get("what_did_not_change") or [])]

    uncertainties: list[str] = []
    if not truth.get("falsifier_usability_improved"):
        uncertainties.append(
            "Filing-public strict pick and sector stratification remain proxy- or blocker-limited for this fixture."
        )
    if truth.get("optimistic_sector_relabel_only"):
        uncertainties.append(
            "Sector moved from 'no row' to 'blank field' in taxonomy only; sector_available is still absent."
        )
    watchpoints: list[str] = [
        "Any newly named filing or sector source/path distinct from Phase 43 bounded paths (see reopen protocol).",
        "Scorecard movement in exact_public_ts_available or sector_available if a bounded retest is authorized later.",
        p46.get("phase46_recommendation") or "hold_closeout_until_named_new_source_or_new_evidence_v1",
    ]

    headline = (
        f"Cohort closed under {ar.get('authoritative_phase')}: "
        f"{str(ar.get('authoritative_recommendation') or '').replace('_', ' ')}. "
        "Hold documented proxy limits until new named evidence or source registration."
    )

    return {
        "asset_id": "research_engine_fixture_cohort_8_row_v1",
        "cohort_row_count": len(rows),
        "cohort_symbols": [str(r.get("symbol") or "") for r in rows],
        "current_stance": str(p46.get("phase46_recommendation") or "hold_closeout"),
        "decision_status": "watching_for_new_evidence",
        "headline_message": headline,
        "what_changed": what_changed,
        "what_did_not_change": what_did_not,
        "current_uncertainties": uncertainties,
        "next_watchpoints": watchpoints,
        "authoritative_phase": str(ar.get("authoritative_phase") or ""),
        "authoritative_recommendation": str(ar.get("authoritative_recommendation") or ""),
        "gate_summary": {
            "gate_status": gate.get("gate_status"),
            "primary_block_category": gate.get("primary_block_category"),
        },
        "closeout_status": st.get("current_closeout_status"),
        "reopen_requires_named_source": bool(fr.get("future_reopen_allowed_with_named_source")),
        "trace_links": {
            "phase45_canonical_closeout_bundle": input_phase45_bundle_path,
            "phase44_claim_narrowing_truthfulness_bundle": input_phase44_bundle_path,
            "phase44_provenance_audit": (phase44_bundle.get("provenance_audit_md_path") or ""),
            "phase44_explanation_v7": (phase44_bundle.get("explanation_v7") or {}).get("path") or "",
        },
    }
