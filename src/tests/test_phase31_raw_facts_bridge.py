"""Phase 31: raw 갭 분류·수리 시맨틱."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sec.facts.concept_map import map_source_concept, normalize_concept_key_for_mapping


def test_normalize_concept_us_gaap_underscore() -> None:
    assert normalize_concept_key_for_mapping("us-gaap_Revenues") == "us-gaap:Revenues"
    c, st = map_source_concept("us-gaap_Revenues")
    assert st == "mapped"
    assert c == "revenue"


def test_classify_raw_facts_gap_sec_pipeline_present() -> None:
    from phase31.raw_facts_gaps import classify_raw_facts_gap_detail

    client = MagicMock()

    def _table(name: str) -> MagicMock:
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.limit.return_value = m
        if name == "filing_index":
            m.execute.return_value = MagicMock(data=[{"id": "1"}])
        elif name == "raw_xbrl_facts":
            m.execute.return_value = MagicMock(data=[])
        elif name == "raw_sec_filings":
            m.execute.return_value = MagicMock(data=[{"id": "r"}])
        return m

    client.table.side_effect = _table
    d = classify_raw_facts_gap_detail(client, cik="0000000001", symbol="X")
    assert d["sub_reason"] == "raw_sec_pipeline_present_xbrl_facts_not_attempted"


def test_report_raw_facts_gap_targets_filters_class() -> None:
    from phase31.raw_facts_gaps import report_raw_facts_gap_targets

    client = MagicMock()
    qrep = {
        "classification_rows": [
            {"symbol": "A", "cik": "0000000001", "class": "filing_index_present_no_raw_facts"},
            {"symbol": "B", "cik": "0000000002", "class": "other"},
        ],
    }

    def _classify(_c: object, *, cik: str, symbol: str = "") -> dict:
        return {
            "cik": cik,
            "symbol": symbol,
            "sub_reason": "test_reason",
            "has_filing_index": True,
            "has_raw_xbrl_facts": False,
            "has_raw_sec_filings": False,
        }

    with patch(
        "phase31.raw_facts_gaps.report_quarter_snapshot_backfill_gaps",
        return_value=qrep,
    ), patch(
        "phase31.raw_facts_gaps.classify_raw_facts_gap_detail",
        side_effect=_classify,
    ):
        out = report_raw_facts_gap_targets(
            client, universe_name="u", panel_limit=10
        )
    assert out["filing_index_present_no_raw_facts_row_count"] == 1
    assert out["unique_cik_count"] == 1


def test_raw_facts_repair_buckets() -> None:
    from phase31.raw_facts_repair import run_raw_facts_backfill_repair

    targets = [
        {
            "symbol": "ZZZ",
            "cik": "0000000001",
            "class": "filing_index_present_no_raw_facts",
        }
    ]

    def _fake_report(*_a: object, **_k: object) -> dict:
        return {"targets": targets}

    def _fake_extract(_cl: object, _st: object, _t: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "cik": "0000000001",
            "raw_inserted": 3,
            "raw_skipped": 0,
            "silver_inserted": 1,
            "accession_no": "a1",
        }

    with patch(
        "phase31.raw_facts_repair.report_raw_facts_gap_targets",
        side_effect=_fake_report,
    ), patch(
        "phase31.raw_facts_repair.run_facts_extract_for_ticker",
        side_effect=_fake_extract,
    ), patch(
        "phase31.raw_facts_repair.classify_cik_quarter_snapshot_gap",
        side_effect=["filing_index_present_no_raw_facts", "raw_present_no_silver_facts"],
    ), patch("db.client.get_supabase_client", return_value=MagicMock()):
        out = run_raw_facts_backfill_repair(
            object(), universe_name="u", panel_limit=10, max_cik_repairs=3
        )
    assert out["repaired_to_raw_present_count"] == 1


def test_phase32_recommend_raw_bridge() -> None:
    from phase31.phase32_recommend import (
        PHASE32_RAW_BRIDGE,
        recommend_phase32_branch,
    )

    before = {
        "missing_quarter_snapshot_for_cik": 10,
        "missing_validation_symbol_count": 5,
        "quarter_snapshot_classification_counts": {
            "filing_index_present_no_raw_facts": 40
        },
    }
    after = dict(before)
    r = recommend_phase32_branch(
        before=before,
        after=after,
        raw_repair={"repaired_to_raw_present_count": 5},
        silver_seam={"actions": []},
    )
    assert r["phase32_recommendation"] == PHASE32_RAW_BRIDGE


def test_write_phase31_review(tmp_path) -> None:
    from pathlib import Path

    from phase31.review import write_phase31_raw_facts_bridge_review_md

    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 0.1,
            "missing_validation_symbol_count": 191,
            "missing_quarter_snapshot_for_cik": 189,
            "factor_panel_missing_for_resolved_cik": 189,
            "quarter_snapshot_classification_counts": {},
        },
        "after": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 0.1,
            "missing_validation_symbol_count": 190,
            "missing_quarter_snapshot_for_cik": 188,
            "factor_panel_missing_for_resolved_cik": 188,
            "quarter_snapshot_classification_counts": {},
        },
        "raw_facts_backfill_repair": {
            "repaired_to_raw_present_count": 2,
            "deferred_external_source_gap_count": 0,
            "blocked_mapping_or_schema_seam_count": 0,
            "facts_extract_attempts": 2,
        },
        "gis_like_silver_seam_repair": {"actions": []},
        "deterministic_empty_cik_issuer_repair": {
            "deterministic_repairs_applied": [],
            "blocked": [],
        },
        "downstream_substrate_retry": {"cik_count": 0},
        "phase32": {"phase32_recommendation": "x", "rationale": "y"},
    }
    p = tmp_path / "p31.md"
    write_phase31_raw_facts_bridge_review_md(str(p), bundle=bundle)
    assert "Phase 31" in Path(p).read_text(encoding="utf-8")
