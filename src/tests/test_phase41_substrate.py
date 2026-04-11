"""Phase 41 substrate classifiers and gate (no DB)."""

from __future__ import annotations

from phase41.phase42_recommend import recommend_phase42_after_phase41
from phase41.promotion_gate_phase41 import build_promotion_gate_phase41
from phase41.substrate_filing import classify_filing_substrate_row, summarize_filing_substrate
from phase41.substrate_sector import classify_sector_substrate_row, summarize_sector_substrate


def test_filing_classify_unavailable_no_rows() -> None:
    r = classify_filing_substrate_row(
        signal_available_date="2025-12-08",
        filing_index_rows=[],
    )
    assert r["classification"] == "filing_public_ts_unavailable"
    assert r["explicit_proxy"] is True
    assert r["filing_bound_source"] == "signal_available_date_proxy"
    assert r["effective_pick_bound_ymd"] == "2025-12-08"


def test_filing_classify_accepted_at() -> None:
    rows = [
        {
            "form": "10-Q",
            "filed_at": "2025-11-01T00:00:00+00:00",
            "accepted_at": "2025-11-02T14:00:00+00:00",
            "accession_no": "0001",
        }
    ]
    r = classify_filing_substrate_row(signal_available_date="2025-12-08", filing_index_rows=rows)
    assert r["classification"] == "exact_filing_public_ts_available"
    assert r["explicit_proxy"] is False
    assert r["acceptance_date_prefix"] == "2025-11-02"
    assert r["effective_pick_bound_ymd"] == "2025-11-02"


def test_filing_classify_filed_only() -> None:
    rows = [
        {
            "form": "10-K",
            "filed_at": "2025-10-15T00:00:00+00:00",
            "accepted_at": None,
            "accession_no": "0002",
        }
    ]
    r = classify_filing_substrate_row(signal_available_date="2025-12-08", filing_index_rows=rows)
    assert r["classification"] == "exact_filing_filed_date_available"
    assert r["explicit_proxy"] is False
    assert r["filed_at_ymd"] == "2025-10-15"


def test_filing_summarize() -> None:
    a = classify_filing_substrate_row(signal_available_date="2025-12-08", filing_index_rows=[])
    b = classify_filing_substrate_row(
        signal_available_date="2025-12-08",
        filing_index_rows=[
            {"form": "10-Q", "filed_at": "2025-11-01T00:00:00Z", "accepted_at": "2025-11-01T16:00:00Z"}
        ],
    )
    s = summarize_filing_substrate(
        [{"symbol": "X", "cik": "1", **a}, {"symbol": "Y", "cik": "2", **b}]
    )
    assert s["row_count"] == 2
    assert s["rows_with_explicit_signal_proxy"] == 1


def test_sector_classify() -> None:
    m = classify_sector_substrate_row(symbol="NVDA", metadata_row=None)
    assert m["classification"] == "sector_metadata_missing"
    m2 = classify_sector_substrate_row(
        symbol="NVDA",
        metadata_row={"sector": "Technology", "industry": "Semiconductors"},
    )
    assert m2["classification"] == "sector_metadata_available"
    assert m2["sector_label"] == "Technology"


def test_sector_summarize() -> None:
    rows = [
        classify_sector_substrate_row(symbol="A", metadata_row={"sector": "Tech"}),
        classify_sector_substrate_row(symbol="B", metadata_row={}),
    ]
    s = summarize_sector_substrate(rows)
    assert s["by_classification"]["sector_metadata_available"] == 1
    assert s["by_classification"]["sector_metadata_missing"] == 1


def test_gate_proxy_substrate() -> None:
    pit = {
        "all_families_leakage_passed": True,
        "families_executed": [
            {"family_id": "signal_filing_boundary_v1", "joined_any_row": False},
            {"family_id": "issuer_sector_reporting_cadence_v1", "joined_any_row": False},
        ],
        "filing_substrate": {
            "summary": {"row_count": 8, "rows_with_explicit_signal_proxy": 3},
        },
        "sector_substrate": {
            "summary": {
                "row_count": 8,
                "by_classification": {"sector_metadata_missing": 2},
            },
        },
    }
    hyps = [{"hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1", "status": "challenged"}]
    g = build_promotion_gate_phase41(prior_gate={"schema_version": 3}, pit_result=pit, hypotheses=hyps)
    assert g["schema_version"] == 4
    assert g["primary_block_category"] == "deferred_due_to_proxy_limited_falsifier_substrate"


def test_gate_no_proxy() -> None:
    pit = {
        "all_families_leakage_passed": True,
        "families_executed": [
            {"family_id": "signal_filing_boundary_v1", "joined_any_row": False},
            {"family_id": "issuer_sector_reporting_cadence_v1", "joined_any_row": False},
        ],
        "filing_substrate": {"summary": {"row_count": 8, "rows_with_explicit_signal_proxy": 0}},
        "sector_substrate": {
            "summary": {
                "row_count": 8,
                "by_classification": {"sector_metadata_available": 8},
            },
        },
    }
    hyps = [{"hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1", "status": "challenged"}]
    g = build_promotion_gate_phase41(prior_gate={}, pit_result=pit, hypotheses=hyps)
    assert g["primary_block_category"] == "conditionally_supported_but_not_promotable"


def test_phase42_recommend() -> None:
    r = recommend_phase42_after_phase41(bundle={})
    assert "phase42_recommendation" in r
