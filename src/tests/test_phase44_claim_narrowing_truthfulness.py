"""DB-free Phase 44: provenance separation, truthfulness, retry registry, claim narrowing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase44.claim_narrowing import build_claim_narrowing
from phase44.orchestrator import run_phase44_claim_narrowing_truthfulness
from phase44.provenance_audit import build_provenance_audit_rows
from phase44.recommendation_truth import assess_phase44_truthfulness
from phase44.retry_eligibility import build_retry_eligibility


def _gate() -> dict:
    return {
        "gate_status": "deferred",
        "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
    }


def _disc() -> dict:
    return {
        "outcome_rollup_signature_by_family": {
            "signal_filing_boundary_v1": "A",
            "issuer_sector_reporting_cadence_v1": "B",
        }
    }


def _minimal_phase43_bundle(*, sector_after_dist: dict, filing_after_dist: dict | None = None) -> dict:
    filing_after_dist = filing_after_dist or {
        "no_10k_10q_rows_for_cik": 7,
        "only_post_signal_filings_available": 1,
    }
    row = {
        "symbol": "TST",
        "cik": "0000000001",
        "signal_available_date": "2025-06-01",
        "filing_blocker_before": "no_10k_10q_rows_for_cik",
        "filing_blocker_after": "no_10k_10q_rows_for_cik",
        "sector_blocker_before": "no_market_metadata_row_for_symbol",
        "sector_blocker_after": "sector_field_blank_on_metadata_row",
        "filing_index_row_count_before": 3,
        "filing_index_row_count_after": 3,
        "n_10k_10q_before": 0,
        "n_10k_10q_after": 0,
        "any_pre_signal_candidate_before": False,
        "any_pre_signal_candidate_after": False,
        "raw_row_count_before": 0,
        "raw_row_count_after": 1,
        "sector_present_before": False,
        "sector_present_after": False,
        "industry_present_before": False,
        "industry_present_after": False,
    }
    return {
        "target_cohort": [
            {
                "symbol": "TST",
                "cik": "0000000001",
                "signal_available_date": "2025-06-01",
                "filing_blocker_cause_before": "no_10k_10q_rows_for_cik",
                "sector_blocker_cause_before": "no_market_metadata_row_for_symbol",
            }
        ],
        "before_after_row_audit": [row],
        "scorecard_before": {
            "filing_blocker_distribution": dict(filing_after_dist),
            "sector_blocker_distribution": {"no_market_metadata_row_for_symbol": 8},
        },
        "scorecard_after": {
            "filing_blocker_distribution": dict(filing_after_dist),
            "sector_blocker_distribution": dict(sector_after_dist),
        },
        "gate_before": _gate(),
        "gate_after": _gate(),
        "phase42_rerun_after_backfill": {"discrimination_summary": _disc()},
        "backfill_actions": {
            "filing": {"repair": "bounded_run_sample_ingest_per_cik"},
            "sector": {"provider": "yahoo_chart"},
        },
    }


def test_provenance_separates_input_bundle_from_runtime_metrics() -> None:
    b = _minimal_phase43_bundle(
        sector_after_dist={"sector_field_blank_on_metadata_row": 8},
    )
    rows = build_provenance_audit_rows(phase43_bundle=b)
    assert len(rows) == 1
    r = rows[0]
    assert r["input_bundle_before"]["sector_blocker"] == "no_market_metadata_row_for_symbol"
    assert r["runtime_snapshot_before_repair"]["raw_row_count"] == 0
    assert r["runtime_snapshot_before_repair"]["sector_blocker"] == "no_market_metadata_row_for_symbol"
    assert r["runtime_snapshot_after_repair"]["raw_row_count"] == 1
    assert r["runtime_snapshot_after_repair"]["sector_blocker"] == "sector_field_blank_on_metadata_row"


def test_blank_field_only_sector_relabel_not_material() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_field_blank_on_metadata_row": 8})
    t = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    assert t["material_falsifier_improvement"] is False
    assert t["optimistic_sector_relabel_only"] is True


def test_sector_available_increase_is_material() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_available": 8})
    b["scorecard_before"]["sector_blocker_distribution"] = {"sector_field_blank_on_metadata_row": 8}
    t = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    assert t["material_falsifier_improvement"] is True
    assert t["falsifier_usability_improved"] is True


def test_exact_public_ts_increase_is_material() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_field_blank_on_metadata_row": 8})
    b["scorecard_before"]["filing_blocker_distribution"] = {
        "no_10k_10q_rows_for_cik": 8,
    }
    b["scorecard_after"]["filing_blocker_distribution"] = {
        "no_10k_10q_rows_for_cik": 7,
        "exact_public_ts_available": 1,
    }
    t = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    assert t["material_falsifier_improvement"] is True
    assert t["falsifier_usability_improved"] is True


def test_unchanged_gate_and_no_falsifier_gain_yields_narrow_claims_path() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_field_blank_on_metadata_row": 8})
    truth = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    retry = build_retry_eligibility(
        phase43_bundle=b,
        material_falsifier_improvement=bool(truth["material_falsifier_improvement"]),
    )
    cn = build_claim_narrowing(
        truth=truth,
        retry=retry,
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
    )
    assert truth["gate_materially_improved"] is False
    assert cn["cohort_claim_limits"]["claim_status"] == "narrowed"
    assert retry["filing_retry_eligible"] is False
    assert retry["sector_retry_eligible"] is False


def test_retry_requires_named_new_source_even_when_material() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_available": 8})
    b["scorecard_before"]["sector_blocker_distribution"] = {"sector_field_blank_on_metadata_row": 8}
    truth = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    assert truth["material_falsifier_improvement"] is True
    retry = build_retry_eligibility(
        phase43_bundle=b,
        material_falsifier_improvement=True,
        declared_new_filing_source=None,
        declared_new_sector_source=None,
    )
    assert retry["filing_retry_eligible"] is False
    assert retry["sector_retry_eligible"] is False


def test_retry_eligible_with_declared_new_sources_and_material() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_available": 8})
    b["scorecard_before"]["sector_blocker_distribution"] = {"sector_field_blank_on_metadata_row": 8}
    truth = assess_phase44_truthfulness(
        scorecard_before=b["scorecard_before"],
        scorecard_after=b["scorecard_after"],
        gate_before=b["gate_before"],
        gate_after=b["gate_after"],
        discrimination_before=_disc(),
        discrimination_after=_disc(),
    )
    retry = build_retry_eligibility(
        phase43_bundle=b,
        material_falsifier_improvement=True,
        declared_new_filing_source="sec_edgar_bulk_secondary_ingest_v2",
        declared_new_sector_source="polygon_sector_fundamentals_v1",
    )
    assert retry["filing_retry_eligible"] is True
    assert retry["sector_retry_eligible"] is True


def test_operator_closeout_bundles_smoke(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p43 = repo / "docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json"
    p42 = repo / "docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json"
    if not p43.is_file() or not p42.is_file():
        pytest.skip("operator closeout bundles not present")
    p43c = tmp_path / "p43.json"
    p42c = tmp_path / "p42.json"
    p43c.write_text(p43.read_text(encoding="utf-8"), encoding="utf-8")
    p42c.write_text(p42.read_text(encoding="utf-8"), encoding="utf-8")
    out = run_phase44_claim_narrowing_truthfulness(
        phase43_bundle_in=str(p43c),
        phase42_supabase_bundle_in=str(p42c),
    )
    assert out["ok"] is True
    assert out["phase"] == "phase44_claim_narrowing_truthfulness"
    assert len(out["provenance_audit"]) == 8
    ta = out["phase44_truthfulness_assessment"]
    assert ta["material_falsifier_improvement"] is False
    assert ta["optimistic_sector_relabel_only"] is True
    assert out["retry_eligibility"]["filing_retry_eligible"] is False
    assert out["phase45"]["phase45_recommendation"] == "narrow_claims_document_proxy_limits_operator_closeout_v1"
    json.dumps(out)


def test_same_phase43_filing_repair_string_not_eligible_as_new_source() -> None:
    b = _minimal_phase43_bundle(sector_after_dist={"sector_available": 8})
    b["scorecard_before"]["sector_blocker_distribution"] = {"sector_field_blank_on_metadata_row": 8}
    retry = build_retry_eligibility(
        phase43_bundle=b,
        material_falsifier_improvement=True,
        declared_new_filing_source="bounded_run_sample_ingest_per_cik",
        declared_new_sector_source="yahoo_chart",
    )
    assert retry["filing_retry_eligible"] is False
    assert retry["sector_retry_eligible"] is False
