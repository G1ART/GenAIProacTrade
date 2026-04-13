"""Single canonical machine-readable closeout summary for the 8-row cohort."""

from __future__ import annotations

from typing import Any


def _unsupported_list(claim_narrowing: dict[str, Any]) -> list[str]:
    out: list[str] = []
    fam = claim_narrowing.get("family_claim_limits") or {}
    for _fid, row in fam.items():
        u = row.get("unsupported_scope")
        if u:
            out.append(str(u))
    cohort = claim_narrowing.get("cohort_claim_limits") or {}
    if cohort.get("unsupported_scope"):
        out.append(str(cohort["unsupported_scope"]))
    return out


def build_canonical_closeout(
    *,
    phase43_bundle: dict[str, Any],
    phase44_bundle: dict[str, Any],
    authoritative_resolution: dict[str, Any],
    future_reopen_protocol: dict[str, Any],
) -> dict[str, Any]:
    cohort_rows: list[dict[str, Any]] = []
    for t in phase43_bundle.get("target_cohort") or []:
        cohort_rows.append(
            {
                "symbol": str(t.get("symbol") or ""),
                "cik": str(t.get("cik") or ""),
                "signal_available_date": str(t.get("signal_available_date") or "")[:10],
            }
        )

    backfill = phase43_bundle.get("backfill_actions") or {}
    filing_bf = backfill.get("filing") or {}
    sector_bf = backfill.get("sector") or {}

    truth = phase44_bundle.get("phase44_truthfulness_assessment") or {}
    sc_before = phase44_bundle.get("scorecard_phase42_supabase_before") or {}
    sc_after = phase44_bundle.get("scorecard_phase43_after") or {}
    gate = phase44_bundle.get("gate_after") or phase44_bundle.get("gate_before") or {}
    cn = phase44_bundle.get("claim_narrowing") or {}

    what_attempted = {
        "phase43_bounded_filing_path": str(filing_bf.get("repair") or "unknown"),
        "phase43_bounded_filing_note": "bounded_run_sample_ingest_per_cik cohort cap (see Phase 43 bundle)",
        "phase43_bounded_sector_path": str(sector_bf.get("provider") or sector_bf.get("status") or "unknown"),
        "phase43_sector_note": "bounded metadata hydration attempt (see Phase 43 bundle)",
    }

    what_changed = [
        {
            "axis": "sector_diagnosis",
            "detail": (
                "Scorecard bucket moved no_market_metadata_row_for_symbol → "
                "sector_field_blank_on_metadata_row (diagnostic precision; not sector_available increase)."
            ),
            "evidence": {
                "sector_scorecard_before": sc_before.get("sector_blocker_distribution"),
                "sector_scorecard_after": sc_after.get("sector_blocker_distribution"),
            },
        },
        {
            "axis": "stable_run_digest",
            "detail": "Phase 42 digest changed across Phase 43 bracket (execution artifact; not standalone falsifier proof).",
            "evidence": {
                "digest_before": phase43_bundle.get("stable_run_digest_before"),
                "digest_after": phase43_bundle.get("stable_run_digest_after"),
            },
        },
    ]

    what_did_not_change = [
        {
            "axis": "filing_scorecard",
            "detail": "Filing blocker distribution unchanged at aggregate level for cohort.",
            "evidence": {
                "filing_distribution_changed": truth.get("filing_distribution_changed"),
                "filing_before": sc_before.get("filing_blocker_distribution"),
                "filing_after": sc_after.get("filing_blocker_distribution"),
            },
        },
        {
            "axis": "sector_available",
            "detail": "No increase in sector_available; sector-informed falsification still unavailable.",
            "evidence": {"falsifier_usability_improved": truth.get("falsifier_usability_improved")},
        },
        {
            "axis": "promotion_gate",
            "detail": "gate_status and primary_block_category unchanged vs Phase 43 bracket.",
            "evidence": {
                "gate_status": gate.get("gate_status"),
                "primary_block_category": gate.get("primary_block_category"),
                "gate_materially_improved": truth.get("gate_materially_improved"),
            },
        },
        {
            "axis": "discrimination_rollups",
            "detail": "Family outcome rollup signatures did not materially change.",
            "evidence": {"discrimination_rollups_improved": truth.get("discrimination_rollups_improved")},
        },
    ]

    reopen_summary = future_reopen_protocol.get("reopen_decision_rule", "")

    return {
        "cohort": {"row_count": len(cohort_rows), "rows": cohort_rows},
        "what_was_attempted": what_attempted,
        "what_changed": what_changed,
        "what_did_not_change": what_did_not_change,
        "authoritative_narrowed_claims": cn,
        "explicit_unsupported_interpretations": _unsupported_list(cn),
        "final_closeout_verdict": authoritative_resolution.get("authoritative_recommendation"),
        "final_closeout_verdict_rationale": authoritative_resolution.get("authoritative_rationale"),
        "reopening_conditions": {
            "summary": reopen_summary,
            "requires_named_new_source": True,
            "forbids_broad_public_core_reopen": True,
        },
        "phase43_legacy_guidance_status": "non_authoritative_for_current_cohort",
        "phase44_authoritative_guidance_status": "authoritative_for_current_cohort",
    }
