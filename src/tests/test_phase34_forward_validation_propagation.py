"""Phase 34 — 전파 분류, validation refresh, 성숙 retry, 가격 ingest, 리뷰/번들."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from phase34.matured_forward_retry import (
    report_matured_forward_retry_targets,
    run_matured_forward_retry,
)
from phase34.orchestrator import run_phase34_forward_validation_propagation
from phase34.price_backfill import (
    run_bounded_price_ingest_for_propagation_missing_windows,
)
from phase34.propagation_audit import (
    classify_propagation_gap,
    export_forward_validation_propagation_gaps,
    report_forward_validation_propagation_gaps,
)
from phase34.review import (
    write_phase34_forward_validation_propagation_bundle_json,
    write_phase34_forward_validation_propagation_review_md,
)
from phase34.validation_refresh import run_validation_refresh_after_forward_propagation


def _bundle32() -> dict:
    return {
        "forward_return_backfill_phase31_touched": {
            "forward_gap_report": {
                "target_entries": [
                    {"symbol": "AAA", "in_missing_excess_return_1q_queue": True},
                ]
            },
            "forward_build": {
                "error_sample": [
                    {
                        "symbol": "ZZZ",
                        "signal_date": "2020-01-15",
                        "horizon": "next_quarter",
                        "error": "insufficient_price_history",
                    }
                ]
            },
        },
    }


def test_classify_propagation_gap_branches() -> None:
    assert (
        classify_propagation_gap(
            validation_excess_1q=None,
            forward_nq_row={"excess_forward_return": 0.01},
            price_classification="would_compute_now",
        )
        == "forward_present_validation_not_refreshed"
    )
    assert (
        classify_propagation_gap(
            validation_excess_1q=None,
            forward_nq_row={"excess_forward_return": 0.01},
            price_classification="would_compute_now",
            refresh_attempt_failed=True,
        )
        == "forward_present_validation_refresh_failed"
    )
    assert (
        classify_propagation_gap(
            validation_excess_1q=0.02,
            forward_nq_row={"excess_forward_return": 0.01},
            price_classification="would_compute_now",
        )
        == "synchronized"
    )
    assert (
        classify_propagation_gap(
            validation_excess_1q=None,
            forward_nq_row=None,
            price_classification="lookahead_window_not_matured",
        )
        == "forward_not_present_window_not_matured"
    )
    assert (
        classify_propagation_gap(
            validation_excess_1q=None,
            forward_nq_row=None,
            price_classification="missing_market_prices_daily_window",
        )
        == "forward_not_present_other_gap"
    )


@patch("phase34.propagation_audit._panel_rows_for_symbols")
@patch("phase34.propagation_audit.classify_price_gap_for_forward_row")
@patch("phase34.propagation_audit._fetch_forward_map")
def test_report_propagation_gaps_counts(
    mock_fwd: MagicMock,
    mock_price: MagicMock,
    mock_panels: MagicMock,
) -> None:
    mock_price.return_value = {"classification": "would_compute_now", "detail": "x"}
    mock_fwd.return_value = {
        "next_quarter": {"excess_forward_return": 0.05},
    }
    mock_panels.return_value = [
        {
            "symbol": "AAA",
            "cik": "1",
            "accession_no": "a",
            "factor_version": "fv1",
            "signal_available_date": "2020-02-01",
            "excess_return_1q": None,
        },
    ]
    client = MagicMock()
    out = report_forward_validation_propagation_gaps(
        client, phase32_bundle=_bundle32(), panel_limit=50
    )
    assert out["forward_row_present_count"] == 1
    assert (
        out["classification_counts"]["forward_present_validation_not_refreshed"] == 1
    )


def test_export_propagation_gaps(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    export_forward_validation_propagation_gaps({"ok": True}, out_json=str(p))
    assert json.loads(p.read_text(encoding="utf-8"))["ok"] is True


@patch("phase34.validation_refresh.run_validation_panel_build_from_rows")
@patch("phase34.validation_refresh.report_forward_metric_truth_audit")
@patch("phase34.validation_refresh.report_forward_validation_propagation_gaps")
def test_validation_refresh_skips_when_no_targets(
    mock_gap: MagicMock,
    mock_truth: MagicMock,
    mock_build: MagicMock,
) -> None:
    mock_gap.return_value = {
        "rows": [
            {
                "classification": "synchronized",
                "cik": "x",
                "accession_no": "a",
                "factor_version": "v",
            }
        ]
    }
    mock_truth.return_value = {
        "symbol_cleared_from_missing_excess_queue_count": 0,
        "joined_recipe_substrate_row_count_live": 1,
    }
    client = MagicMock()
    settings = MagicMock()
    out = run_validation_refresh_after_forward_propagation(
        settings,
        client,
        universe_name="u",
        phase32_bundle=_bundle32(),
    )
    assert out.get("skipped") is True
    mock_build.assert_not_called()


@patch("phase34.matured_forward_retry.report_forward_metric_truth_audit")
@patch("phase34.matured_forward_retry.run_forward_returns_build_from_rows")
@patch("phase34.matured_forward_retry.get_supabase_client")
@patch("phase34.matured_forward_retry.classify_price_gap_for_forward_row")
def test_matured_retry_skips_when_none_eligible(
    mock_cls: MagicMock,
    mock_cli: MagicMock,
    mock_build: MagicMock,
    mock_truth: MagicMock,
) -> None:
    mock_cls.return_value = {
        "classification": "lookahead_window_not_matured",
        "detail": "x",
    }
    mock_cli.return_value = MagicMock()
    mock_truth.return_value = {}
    settings = MagicMock()
    out = run_matured_forward_retry(
        settings, universe_name="u", phase32_bundle=_bundle32()
    )
    assert out.get("skipped") is True
    mock_build.assert_not_called()
    rep = report_matured_forward_retry_targets(
        mock_cli.return_value, phase32_bundle=_bundle32()
    )
    assert rep["maturity_eligible_count"] == 0
    assert rep["still_not_matured_count"] >= 1


@patch("phase34.price_backfill.run_market_prices_ingest_for_symbols")
def test_price_backfill_only_missing_window(mock_ing: MagicMock) -> None:
    mock_ing.return_value = {"status": "completed"}
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"px": 1}
    ]
    settings = MagicMock()
    gap = {
        "rows": [
            {
                "symbol": "X",
                "signal_available_date": "2020-06-01",
                "price_gap": {"classification": "lookahead_window_not_matured"},
            },
            {
                "symbol": "Y",
                "signal_available_date": "2020-06-01",
                "price_gap": {
                    "classification": "missing_market_prices_daily_window"
                },
            },
        ]
    }
    with patch(
        "phase34.price_backfill.dbrec.fetch_silver_prices_for_symbol_range",
        return_value=[{"d": 1}],
    ):
        out = run_bounded_price_ingest_for_propagation_missing_windows(
            settings, client, propagation_gap_report=gap
        )
    assert out["ingest_attempted"] is True
    mock_ing.assert_called_once()
    call_kw = mock_ing.call_args[1]
    assert call_kw["symbols"] == ["Y"]


def test_phase34_review_and_bundle(tmp_path: Path) -> None:
    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 2,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
        },
        "after": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 0.9,
            "missing_excess_return_1q": 1,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
        },
        "propagation_gap_before": {
            "classification_counts": {"forward_present_validation_not_refreshed": 3}
        },
        "propagation_gap_final": {
            "classification_counts": {"forward_present_validation_not_refreshed": 1}
        },
        "closeout_summary": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 0.9,
            "missing_excess_return_1q": 1,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
            "forward_row_present_count": 5,
            "validation_excess_filled_now_count": 2,
            "symbol_cleared_from_missing_excess_queue_count": 1,
            "joined_recipe_unlocked_now_count": 1,
            "matured_forward_retry_success_count": 0,
            "still_not_matured_count": 7,
            "price_coverage_repaired_now_count": 0,
            "gis_outcome": "blocked",
            "gis_blocked_reason": "sample",
            "phase35": {
                "phase35_recommendation": "next",
                "rationale": "r",
            },
        },
        "phase35": {"phase35_recommendation": "next", "rationale": "r"},
    }
    md = tmp_path / "r.md"
    bj = tmp_path / "b.json"
    write_phase34_forward_validation_propagation_review_md(str(md), bundle=bundle)
    write_phase34_forward_validation_propagation_bundle_json(str(bj), bundle=bundle)
    assert "Phase 34" in md.read_text(encoding="utf-8")
    assert json.loads(bj.read_text(encoding="utf-8"))["closeout_summary"][
        "forward_row_present_count"
    ] == 5


@patch("phase34.orchestrator.inspect_gis_raw_present_no_silver_deterministic")
@patch("phase34.orchestrator.report_quarter_snapshot_backfill_gaps")
@patch("phase34.orchestrator.report_factor_panel_materialization_gaps")
@patch("phase34.orchestrator.report_validation_registry_gaps")
@patch("phase34.orchestrator.report_forward_validation_propagation_gaps")
@patch("phase34.orchestrator.run_bounded_price_ingest_for_propagation_missing_windows")
@patch("phase34.orchestrator.run_matured_forward_retry")
@patch("phase34.orchestrator.report_matured_forward_retry_targets")
@patch("phase34.orchestrator.run_validation_refresh_after_forward_propagation")
@patch("phase34.orchestrator.collect_phase33_substrate_snapshot")
@patch("phase34.orchestrator.get_supabase_client")
@patch("phase34.orchestrator.load_phase32_bundle")
def test_orchestrator_smoke(
    mock_lb: MagicMock,
    mock_cli: MagicMock,
    mock_snap: MagicMock,
    mock_vr: MagicMock,
    mock_mt: MagicMock,
    mock_mf: MagicMock,
    mock_pb: MagicMock,
    mock_gap: MagicMock,
    mock_rv: MagicMock,
    mock_mat: MagicMock,
    mock_q: MagicMock,
    mock_gis: MagicMock,
) -> None:
    mock_lb.return_value = _bundle32()
    mock_cli.return_value = MagicMock()
    snap = {
        "joined_recipe_substrate_row_count": 10,
        "thin_input_share": 1.0,
        "missing_excess_return_1q": 5,
        "missing_validation_symbol_count": 0,
        "missing_quarter_snapshot_for_cik": 0,
        "factor_panel_missing_for_resolved_cik": 0,
    }
    mock_snap.side_effect = [snap, snap]
    mock_gap.return_value = {
        "rows": [],
        "forward_row_present_count": 0,
        "classification_counts": {},
    }
    mock_vr.return_value = {
        "refresh_failed_keys": [],
        "validation_excess_filled_now_count": 0,
        "metric_truth_before": {"symbol_cleared_from_missing_excess_queue_count": 0},
        "metric_truth_after": {"symbol_cleared_from_missing_excess_queue_count": 0},
    }
    mock_mt.return_value = {"still_not_matured_count": 1}
    mock_mf.return_value = {"matured_forward_retry_success_count": 0}
    mock_pb.return_value = {"price_coverage_repaired_now_count": 0}
    mock_rv.return_value = {}
    mock_mat.return_value = {}
    mock_q.return_value = {"classification_counts": {}}
    mock_gis.return_value = {"outcome": "ok", "blocked_reason": None}

    settings = MagicMock()
    out = run_phase34_forward_validation_propagation(
        settings,
        universe_name="u",
        phase32_bundle_path="/tmp/x.json",
    )
    assert out["ok"] is True
    assert "closeout_summary" in out
