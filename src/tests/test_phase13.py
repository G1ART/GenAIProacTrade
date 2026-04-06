"""Phase 13: public-core quality gate + residual triage regression guards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from casebook.residual_triage import assign_residual_triage_fields
from public_core.quality import (
    classify_cycle_quality,
    collect_cycle_metrics,
    rank_gap_reasons,
    transcripts_overlay_coarse,
)


def test_classify_cycle_quality_failed_when_not_ok() -> None:
    m = {"candidates_scanned": 10, "stage_status_by_name": {}}
    assert classify_cycle_quality(cycle_ok=False, scanner_failed=False, metrics=m) == "failed"
    assert classify_cycle_quality(cycle_ok=True, scanner_failed=True, metrics=m) == "failed"


def test_classify_cycle_quality_degraded_on_stage_failed() -> None:
    m = {
        "candidates_scanned": 10,
        "insufficient_data_fraction": 0.1,
        "gating_high_missingness_fraction": 0,
        "watchlist_selected": 2,
        "casebook_entries_created": 2,
        "stage_status_by_name": {"harness_inputs": "failed"},
    }
    assert classify_cycle_quality(cycle_ok=True, scanner_failed=False, metrics=m) == "degraded"


def test_classify_cycle_quality_thin_input_high_insufficient() -> None:
    m = {
        "candidates_scanned": 100,
        "insufficient_data_fraction": 0.8,
        "gating_high_missingness_fraction": 0,
        "watchlist_selected": 0,
        "casebook_entries_created": 0,
        "stage_status_by_name": {},
        "harness_error_rate": 0,
    }
    assert classify_cycle_quality(cycle_ok=True, scanner_failed=False, metrics=m) == "thin_input"


def test_classify_cycle_quality_strong() -> None:
    m = {
        "candidates_scanned": 50,
        "insufficient_data_fraction": 0.2,
        "gating_high_missingness_fraction": 0.05,
        "watchlist_selected": 3,
        "casebook_entries_created": 2,
        "stage_status_by_name": {},
        "harness_error_rate": 0,
    }
    assert classify_cycle_quality(cycle_ok=True, scanner_failed=False, metrics=m) == "strong"


def test_rank_gap_reasons_non_empty_when_empty_watchlist() -> None:
    m = {
        "candidates_scanned": 20,
        "insufficient_data_fraction": 0.1,
        "gating_high_missingness_fraction": 0,
        "watchlist_selected": 0,
        "harness_error_rate": 0,
        "harness_error_count": 0,
        "casebook_entries_created": 0,
        "memo_touch_rate": 1.0,
        "harness_inputs_built": 10,
    }
    r = rank_gap_reasons(m)
    codes = {x["reason_code"] for x in r}
    assert "empty_watchlist_after_thresholding" in codes


def test_collect_cycle_metrics_merges_stages() -> None:
    stages = [
        {"name": "harness_inputs", "status": "success", "out": {"inputs_built": 10, "errors": []}},
        {
            "name": "investigation_memos",
            "status": "success",
            "out": {"memos_inserted_new_version": 3, "memos_replaced_in_place": 1, "errors": []},
        },
        {
            "name": "outlier_casebook",
            "status": "success",
            "out": {"entries_created": 4, "candidates_scanned": 10},
        },
        {
            "name": "scanner_watchlist",
            "status": "success",
            "out": {"watchlist_entries": 2, "stats": {"candidates_scanned": 10}},
        },
    ]
    client = MagicMock()
    with patch(
        "public_core.quality.dbrec.fetch_state_change_candidate_class_counts",
        return_value={"insufficient_data": 3, "investigate_now": 7},
    ), patch(
        "public_core.quality.dbrec.fetch_state_change_gating_and_candidate_count",
        return_value=(1, 10),
    ):
        m = collect_cycle_metrics(client, state_change_run_id="r1", stages=stages)
    assert m["candidates_scanned"] == 10
    assert m["casebook_entries_created"] == 4
    assert m["watchlist_selected"] == 2
    assert m["memos_touched"] == 4


def test_transcripts_overlay_coarse() -> None:
    assert transcripts_overlay_coarse({}) == "absent"
    assert transcripts_overlay_coarse({"error": "row_not_found"}) == "absent"
    assert transcripts_overlay_coarse({"availability": "available"}) == "available"
    assert transcripts_overlay_coarse({"availability": "partial"}) == "partial"


def test_residual_triage_bucket_reaction_gap() -> None:
    e = {
        "outlier_type": "reaction_gap",
        "source_trace": {"validation_panel_id": "vp1"},
        "contamination_regime_missingness_json": {},
    }
    assign_residual_triage_fields(e)
    assert e["residual_triage_bucket"] == "delayed_market_recognition"
    e2 = {
        "outlier_type": "reaction_gap",
        "source_trace": {},
        "contamination_regime_missingness_json": {},
    }
    assign_residual_triage_fields(e2)
    assert e2["residual_triage_bucket"] == "likely_exogenous_event"


def test_residual_triage_bucket_maps_all_types() -> None:
    for ot, expected in (
        ("contamination_override", "data_missingness_dominated"),
        ("regime_mismatch", "regime_mismatch"),
        ("persistence_failure", "regime_mismatch"),
        ("thesis_challenge_divergence", "contradictory_public_signal"),
        ("unexplained_residual", "unresolved_residual"),
    ):
        e = {"outlier_type": ot, "source_trace": {}, "contamination_regime_missingness_json": {}}
        assign_residual_triage_fields(e)
        assert e["residual_triage_bucket"] == expected, ot
        assert e.get("premium_overlay_suggestion")


def test_cycle_summary_includes_quality_keys(tmp_path) -> None:
    from public_core.cycle import run_public_core_cycle

    with patch(
        "db.records.fetch_latest_state_change_run_id", return_value="sc-run-1"
    ), patch(
        "state_change.reports.build_state_change_run_report",
        return_value={"ok": True},
    ), patch(
        "harness.input_materializer.materialize_inputs_for_run",
        return_value={"inputs_built": 0, "errors": []},
    ), patch(
        "harness.run_batch.generate_memos_for_run",
        return_value={"memos_inserted_new_version": 0, "errors": []},
    ), patch(
        "casebook.build_run.run_outlier_casebook_build",
        return_value={"entries_created": 0, "casebook_run_id": "cb1"},
    ), patch(
        "scanner.daily_build.run_daily_scanner_build",
        return_value={
            "watchlist_entries": 0,
            "scanner_run_id": "sr1",
            "stats": {"candidates_scanned": 5},
        },
    ), patch(
        "sources.transcripts_ingest.report_transcripts_overlay_status",
        return_value={"availability": "not_available_yet"},
    ), patch(
        "sources.reporting.build_source_registry_report", return_value={"ok": True}
    ), patch("db.records.fetch_operational_runs_recent", return_value=[]), patch(
        "public_core.quality.compute_cycle_quality_bundle",
        return_value={
            "row_for_insert": {
                "state_change_run_id": "sc-run-1",
                "universe_name": "sp500_current",
                "cycle_finished_ok": True,
                "quality_class": "thin_input",
                "metrics_json": {},
                "gap_reasons_ranked": [],
                "overlay_status_json": {},
                "residual_triage_json": {},
                "unresolved_residual_items": [],
            },
            "quality_class": "thin_input",
            "metrics": {
                "candidates_scanned": 5,
                "insufficient_data_fraction": 0.9,
                "gating_high_missingness_fraction": 0,
                "watchlist_selected": 0,
                "casebook_entries_created": 0,
                "memos_touched": 0,
                "harness_inputs_built": 0,
            },
            "gap_reasons_ranked": [{"rank": 1, "reason_code": "x", "detail": "d", "weight": 1}],
            "overlay_status_json": {"transcripts_coarse": "absent"},
            "residual_triage": {"dominant_bucket": "data_missingness_dominated", "bucket_counts": {"data_missingness_dominated": 3}},
            "unresolved_residual_items": [{"candidate_id": "c1"}],
        },
    ), patch("db.records.insert_public_core_cycle_quality_run", return_value="q1"):
        out = run_public_core_cycle(
            MagicMock(),
            MagicMock(),
            universe="sp500_current",
            out_dir=tmp_path,
        )
    assert out.get("cycle_quality_class") == "thin_input"
    assert out.get("public_core_cycle_quality_run_id") == "q1"
    assert out.get("cycle_quality_snapshot", {}).get("metrics")
    text = (tmp_path / "operator_packet.md").read_text(encoding="utf-8")
    assert "Phase 13 quality gate" in text
    assert "unresolved" in text.lower() or "Residual triage" in text
