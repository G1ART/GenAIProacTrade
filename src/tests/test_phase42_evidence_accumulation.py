"""Phase 42 — taxonomy, discrimination, gate, digest, narrowing (no DB)."""

from __future__ import annotations

from phase42.blocker_taxonomy import classify_filing_blocker_cause, classify_sector_blocker_cause
from phase42.evidence_accumulation import (
    build_discrimination_summary,
    build_family_evidence_scorecard,
    build_row_level_blockers_from_phase41_substrate,
    stable_run_digest,
)
from phase42.explanation_v5 import render_phase42_explanation_v5_md
from phase42.hypothesis_narrowing import narrow_families_for_phase42
from phase42.phase43_recommend import recommend_phase43_after_phase42
from phase42.promotion_gate_phase42 import (
    DEFERRED_NON_DISC,
    DEFERRED_PROXY,
    build_promotion_gate_phase42,
)


def test_classify_filing_empty_index() -> None:
    r = classify_filing_blocker_cause(signal_available_date="2024-01-15", filing_index_rows=[])
    assert r["filing_blocker_cause"] == "no_filing_index_rows_for_cik"


def test_classify_sector_missing() -> None:
    r = classify_sector_blocker_cause(metadata_row=None)
    assert r["sector_blocker_cause"] == "no_market_metadata_row_for_symbol"


def test_discrimination_identical_two_families() -> None:
    fam = {
        "family_id": "x",
        "summary_counts_by_spec": {"s": {"a": 1, "b": 2}},
    }
    d = build_discrimination_summary(families_executed=[fam, {**fam, "family_id": "y"}])
    assert d["any_family_outcome_discriminating"] is False
    assert len(d["families_with_identical_rollups_groups"][0]) == 2


def test_gate_proxy_over_non_disc() -> None:
    pit = {"all_families_leakage_passed": True}
    score = {
        "cohort_row_count": 2,
        "filing_blocker_distribution": {"exact_public_ts_available": 1},
        "sector_blocker_distribution": {"sector_available": 2},
    }
    disc = {"any_family_outcome_discriminating": False}
    narrow = {"headline": "no_outcome_discrimination_across_rerun_families"}
    g = build_promotion_gate_phase42(
        prior_gate={},
        phase41_pit=pit,
        scorecard=score,
        discrimination_summary=disc,
        narrowing=narrow,
        hypotheses=[],
    )
    assert g["primary_block_category"] == DEFERRED_PROXY


def test_gate_non_disc_when_clean_substrate() -> None:
    pit = {"all_families_leakage_passed": True}
    score = {
        "cohort_row_count": 2,
        "filing_blocker_distribution": {
            "exact_public_ts_available": 1,
            "accepted_at_missing_but_filed_date_only": 1,
        },
        "sector_blocker_distribution": {"sector_available": 2},
    }
    disc = {"any_family_outcome_discriminating": False}
    narrow = {"headline": "no_outcome_discrimination_across_rerun_families"}
    g = build_promotion_gate_phase42(
        prior_gate={},
        phase41_pit=pit,
        scorecard=score,
        discrimination_summary=disc,
        narrowing=narrow,
        hypotheses=[],
    )
    assert g["primary_block_category"] == DEFERRED_NON_DISC


def test_stable_run_digest_stable() -> None:
    core = {
        "family_evidence_scorecard": {
            "filing_blocker_distribution": {"a": 1},
            "sector_blocker_distribution": {"b": 2},
        },
        "discrimination_summary": {"families_with_identical_rollups_groups": []},
        "promotion_gate_phase42": {"primary_block_category": "x"},
    }
    assert stable_run_digest(bundle_core=core) == stable_run_digest(bundle_core=core)


def test_row_blockers_from_substrate_replay() -> None:
    pit = {
        "families_executed": [
            {
                "family_id": "signal_filing_boundary_v1",
                "row_results": [
                    {"symbol": "AAA", "cik": "1", "signal_available_date": "2025-06-01"},
                ],
            }
        ],
        "filing_substrate": {
            "per_row": [
                {"symbol": "AAA", "cik": "1", "classification": "exact_filing_public_ts_available"}
            ]
        },
        "sector_substrate": {
            "per_row": [{"symbol": "AAA", "cik": "1", "classification": "sector_metadata_available"}]
        },
    }
    rows = build_row_level_blockers_from_phase41_substrate(pit)
    assert rows[0]["filing_blocker_cause"] == "exact_public_ts_available"
    assert rows[0]["sector_blocker_cause"] == "sector_available"
    assert rows[0]["signal_available_date"] == "2025-06-01"


def test_narrowing_and_explanation_smoke() -> None:
    families = [
        {"family_id": "signal_filing_boundary_v1"},
        {"family_id": "issuer_sector_reporting_cadence_v1"},
    ]
    disc = build_discrimination_summary(
        families_executed=[
            {
                "family_id": "signal_filing_boundary_v1",
                "summary_counts_by_spec": {"s": {"x": 1}},
            },
            {
                "family_id": "issuer_sector_reporting_cadence_v1",
                "summary_counts_by_spec": {"s": {"x": 1}},
            },
        ]
    )
    rows = [
        {
            "filing_blocker_cause": "exact_public_ts_available",
            "sector_blocker_cause": "sector_available",
        }
    ]
    sc = build_family_evidence_scorecard(
        phase41_pit={"families_executed": families},
        row_level_blockers=rows,
        discrimination_summary=disc,
    )
    density = {"by_family": {}, "cohort_row_count": 1}
    narrow = narrow_families_for_phase42(
        families_executed=families,
        discrimination_summary=disc,
        row_level_blockers=rows,
        evidence_density=density,
    )
    gate = build_promotion_gate_phase42(
        prior_gate={},
        phase41_pit={"all_families_leakage_passed": True},
        scorecard=sc,
        discrimination_summary=disc,
        narrowing=narrow,
        hypotheses=[{"hypothesis_id": "h1", "status": "live"}],
    )
    bundle = {
        "family_evidence_scorecard": sc,
        "discrimination_summary": disc,
        "hypothesis_narrowing": narrow,
        "promotion_gate_phase42": gate,
        "stable_run_digest": "abc",
        "phase43": recommend_phase43_after_phase42(bundle={"promotion_gate_phase42": gate}),
    }
    md = render_phase42_explanation_v5_md(bundle=bundle)
    assert "Phase 42 v5" in md
    assert "Promotion gate" in md
