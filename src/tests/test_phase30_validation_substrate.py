"""Phase 30: filing/silver/empty_cik 분류·수리·하류 연쇄."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_report_filing_index_gap_targets_filters_class() -> None:
    from phase30.filing_index_gaps import report_filing_index_gap_targets

    client = MagicMock()
    qrep = {
        "classification_rows": [
            {"symbol": "A", "cik": "0000000001", "class": "no_filing_index_for_cik"},
            {"symbol": "B", "cik": "0000000002", "class": "other"},
            {"symbol": "C", "cik": "0000000001", "class": "no_filing_index_for_cik"},
        ],
    }
    with patch(
        "phase30.filing_index_gaps.report_quarter_snapshot_backfill_gaps",
        return_value=qrep,
    ):
        out = report_filing_index_gap_targets(
            client, universe_name="u", panel_limit=100
        )
    assert out["no_filing_index_row_count"] == 2
    assert out["no_filing_index_unique_cik_count"] == 1
    assert len(out["targets"]) == 1


def test_run_filing_index_backfill_buckets() -> None:
    from phase30.filing_index_gaps import run_filing_index_backfill_repair

    targets = [{"symbol": "ZZZ", "cik": "0000000001", "class": "no_filing_index_for_cik"}]

    def _fake_report(*_a: object, **_k: object) -> dict:
        return {"targets": targets}

    def _fake_ingest(_ticker: str, _settings: object, *, client: object) -> dict:
        return {
            "cik": "0000000001",
            "filing_index_inserted": True,
            "filing_index_updated": False,
        }

    mock_cli = MagicMock()
    ch = mock_cli.table.return_value
    ch.select.return_value = ch
    ch.eq.return_value = ch
    ch.limit.return_value = ch
    ch.execute.return_value = MagicMock(data=[])

    with patch(
        "phase30.filing_index_gaps.report_filing_index_gap_targets",
        side_effect=_fake_report,
    ), patch(
        "phase30.filing_index_gaps.run_sample_ingest",
        side_effect=_fake_ingest,
    ), patch(
        "phase30.filing_index_gaps.classify_cik_quarter_snapshot_gap",
        return_value="filing_index_present_no_raw_facts",
    ), patch(
        "phase30.filing_index_gaps.dbrec.fetch_issuer_quarter_snapshots_for_cik",
        return_value=[],
    ), patch("db.client.get_supabase_client", return_value=mock_cli):
        out = run_filing_index_backfill_repair(
            object(), universe_name="u", panel_limit=50, max_cik_repairs=5
        )
    assert out["repaired_now_count"] == 1
    assert out["filing_index_repaired_now_count"] == 1
    assert out["raw_xbrl_present_after_filing_ingest_count"] == 0
    assert out["blocked_identity_or_mapping_issue_count"] == 0


def test_materialize_silver_from_raw_inserts_when_missing() -> None:
    from phase30.silver_materialization import materialize_silver_from_raw_for_cik

    client = MagicMock()
    t = client.table.return_value
    t.select.return_value = t
    t.eq.return_value = t
    t.limit.return_value = t
    t.execute.return_value = MagicMock(data=[{"accession_no": "acc1"}])

    raw_row = {
        "cik": "1",
        "accession_no": "acc1",
        "concept": "us-gaap:Revenues",
        "dedupe_key": "d1",
        "taxonomy": "us-gaap",
        "unit": "USD",
        "value_numeric": 1.0,
        "period_start": "2024-01-01",
        "period_end": "2024-03-31",
        "instant_date": None,
        "fiscal_year": 2024,
        "fiscal_period": "Q1",
        "source_payload_json": {"period_type": "duration"},
    }

    with patch(
        "phase30.silver_materialization.dbrec.fetch_raw_xbrl_facts_for_filing",
        return_value=[raw_row],
    ), patch(
        "phase30.silver_materialization.dbrec.silver_xbrl_fact_exists",
        return_value=False,
    ), patch(
        "phase30.silver_materialization.dbrec.insert_silver_xbrl_fact"
    ) as ins:
        mo = materialize_silver_from_raw_for_cik(client, cik="1")
    assert mo["silver_inserted"] >= 1
    ins.assert_called()


def test_report_empty_cik_diagnosis_blocked_no_symbol() -> None:
    from phase30.empty_cik_cleanup import report_empty_cik_gaps

    client = MagicMock()
    qrep = {
        "classification_rows": [
            {"symbol": "", "cik": "", "class": "empty_cik"},
        ],
    }
    with patch(
        "phase30.empty_cik_cleanup.report_quarter_snapshot_backfill_gaps",
        return_value=qrep,
    ), patch(
        "phase30.empty_cik_cleanup.compute_substrate_coverage",
        return_value=({"as_of_date": "2024-06-01"}, {}),
    ):
        out = report_empty_cik_gaps(client, universe_name="u", panel_limit=10)
    assert out["empty_cik_row_count"] == 1
    assert out["diagnoses"][0]["diagnosis"] == "blocked_no_symbol"


def test_downstream_cascade_only_passed_ciks() -> None:
    from phase30.downstream_cascade import run_downstream_substrate_cascade_for_ciks

    client = MagicMock()
    with patch(
        "phase30.downstream_cascade.find_silver_accession_without_snapshot",
        return_value=None,
    ), patch(
        "phase30.downstream_cascade.run_factor_panels_for_cik",
        return_value={"ok": True},
    ), patch(
        "phase30.downstream_cascade.dbrec.fetch_issuer_quarter_factor_panels_for_ciks",
        return_value={},
    ):
        out = run_downstream_substrate_cascade_for_ciks(
            object(), client, ciks=["0000000001", "0000000002"], ticker_hints={}
        )
    assert out["cik_count"] == 2
    assert len(out["per_cik"]) == 2


def test_phase31_recommend_prefers_sec_when_filing_dominates() -> None:
    from phase30.phase31_recommend import (
        PHASE31_EXPAND_SEC_INGEST,
        recommend_phase31_branch,
    )

    before = {
        "missing_quarter_snapshot_for_cik": 189,
        "missing_validation_symbol_count": 191,
        "quarter_snapshot_classification_counts": {"no_filing_index_for_cik": 187},
    }
    after = dict(before)
    r = recommend_phase31_branch(
        before=before,
        after=after,
        filing_repair={"repaired_now_count": 0},
        silver_repair={"actions": []},
    )
    assert r["phase31_recommendation"] == PHASE31_EXPAND_SEC_INGEST


def test_write_phase30_review_md(tmp_path) -> None:
    from phase30.review import write_phase30_validation_substrate_review_md

    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 0.5,
            "missing_validation_symbol_count": 10,
            "missing_quarter_snapshot_for_cik": 5,
            "factor_panel_missing_for_resolved_cik": 3,
            "quarter_snapshot_classification_counts": {"no_filing_index_for_cik": 4},
        },
        "after": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 0.5,
            "missing_validation_symbol_count": 9,
            "missing_quarter_snapshot_for_cik": 4,
            "factor_panel_missing_for_resolved_cik": 2,
            "quarter_snapshot_classification_counts": {"no_filing_index_for_cik": 3},
        },
        "filing_index_backfill_repair": {
            "repaired_now_count": 1,
            "deferred_external_source_gap_count": 0,
            "blocked_identity_or_mapping_issue_count": 0,
            "network_ingest_attempts": 1,
            "preflight_unique_targets_count": 5,
        },
        "silver_facts_materialization_repair": {
            "cik_repairs_attempted": 1,
            "actions": [{"cik": "1"}],
        },
        "empty_cik_cleanup": {
            "note": "classification_only",
            "report": {"diagnoses": [{"symbol": "X"}]},
        },
        "downstream_substrate_cascade": {"cik_count": 1},
        "phase31": {
            "phase31_recommendation": "continue_bounded_sec_substrate_ingest",
            "rationale": "test",
        },
    }
    p = tmp_path / "r.md"
    path = write_phase30_validation_substrate_review_md(str(p), bundle=bundle)
    text = Path(path).read_text(encoding="utf-8")
    assert "Phase 30" in text
    assert "missing_validation_symbol_count" in text
    assert "phase31_recommendation" in text or "continue_bounded" in text
