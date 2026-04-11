"""Phase 33 — metric truth separation, price classification, review."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from phase33.metric_truth_audit import (
    export_forward_metric_truth_audit,
    report_forward_metric_truth_audit,
)
from phase33.phase32_bundle_io import (
    phase32_insufficient_price_errors_next_q,
    phase32_touched_symbols,
)
from phase33.price_coverage import classify_price_gap_for_forward_row
from phase33.review import (
    write_phase33_forward_coverage_truth_bundle_json,
    write_phase33_forward_coverage_truth_review_md,
)


def _minimal_phase32_bundle() -> dict:
    return {
        "before": {"joined_recipe_substrate_row_count": 243},
        "after": {"missing_excess_return_1q": 101},
        "forward_return_backfill_phase31_touched": {
            "forward_gap_report": {
                "target_entries": [
                    {
                        "symbol": "AAA",
                        "in_missing_excess_return_1q_queue": True,
                    },
                    {
                        "symbol": "BBB",
                        "in_missing_excess_return_1q_queue": True,
                    },
                ]
            },
            "per_symbol_after": {
                "AAA": {"forward_return_unblocked_now": True},
            },
            "repaired_to_forward_present": 1,
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


def test_phase32_bundle_io_symbols_and_errors() -> None:
    b = _minimal_phase32_bundle()
    assert "AAA" in phase32_touched_symbols(b)
    errs = phase32_insufficient_price_errors_next_q(b)
    assert len(errs) == 1 and errs[0]["symbol"] == "ZZZ"


@patch("phase33.metric_truth_audit._panel_rows_for_symbols")
@patch("phase33.metric_truth_audit.compute_substrate_coverage")
def test_metric_truth_audit_separates_queue(
    mock_cov: MagicMock,
    mock_panels: MagicMock,
) -> None:
    mock_cov.return_value = (
        {"joined_recipe_substrate_row_count": 250},
        {"missing_excess_return_1q": 5},
    )
    mock_cov.side_effect = None
    queues: dict[str, list[str]] = {}

    def _side(
        *args: object, symbol_queues_out: dict | None = None, **kwargs: object
    ) -> tuple[dict, dict]:
        if symbol_queues_out is not None:
            symbol_queues_out["missing_excess_return_1q"] = ["BBB"]
        return (
            {"joined_recipe_substrate_row_count": 250},
            {"missing_excess_return_1q": 5},
        )

    mock_cov.side_effect = _side
    mock_panels.return_value = [
        {"symbol": "AAA", "excess_return_1q": None},
        {"symbol": "BBB", "excess_return_1q": 0.01},
    ]
    client = MagicMock()
    out = report_forward_metric_truth_audit(
        client,
        universe_name="u",
        phase32_bundle=_minimal_phase32_bundle(),
        panel_limit=100,
    )
    assert out["symbol_cleared_from_missing_excess_queue_count"] == 1
    assert out["touched_symbols_still_in_missing_excess_queue"] == ["BBB"]


def test_export_metric_truth_audit_tmp(tmp_path: Path) -> None:
    rep = {"ok": True}
    p = tmp_path / "t.json"
    export_forward_metric_truth_audit(rep, out_json=str(p))
    assert json.loads(p.read_text(encoding="utf-8"))["ok"] is True


@patch("phase33.price_coverage.dbrec.fetch_silver_prices_for_symbol_range")
def test_classify_price_missing_window(mock_sp: MagicMock) -> None:
    mock_sp.return_value = []
    client = MagicMock()
    out = classify_price_gap_for_forward_row(
        client, symbol="X", signal_date_s="2020-06-01"
    )
    assert out["classification"] == "missing_market_prices_daily_window"


def test_write_phase33_review(tmp_path: Path) -> None:
    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 2,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
            "quarter_snapshot_classification_counts": {},
        },
        "after": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 0.9,
            "missing_excess_return_1q": 1,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
            "quarter_snapshot_classification_counts": {},
        },
        "quarter_snapshot_classification_counts_after": {"x": 1},
        "stage_semantics_truth": {
            "forward_row_unblocked_now_count": 3,
            "symbol_cleared_from_missing_excess_queue_count": 1,
            "joined_recipe_unlocked_now_count": 1,
            "price_coverage_repaired_now_count": 0,
            "validation_panel_excess_null_rows_touched_set_live": 4,
        },
        "metric_truth_audit_after": {
            "why_repaired_count_did_not_reduce_headline_excess": "test explanation"
        },
        "price_coverage_gap_report": {"classification_counts": {"a": 1}},
        "price_coverage_backfill": {
            "price_coverage_repaired_now_count": 0,
            "price_coverage_deferred_count": 0,
            "price_coverage_blocked_count": 0,
        },
        "gis_deterministic_inspect": {"outcome": "ok", "blocked_reason": None},
        "phase34": {"phase34_recommendation": "r", "rationale": "t"},
    }
    md = tmp_path / "r.md"
    bj = tmp_path / "b.json"
    write_phase33_forward_coverage_truth_review_md(str(md), bundle=bundle)
    write_phase33_forward_coverage_truth_bundle_json(str(bj), bundle=bundle)
    assert "Truth semantics" in md.read_text(encoding="utf-8")
    assert json.loads(bj.read_text(encoding="utf-8"))["phase34"]["rationale"] == "t"


@patch("phase33.forward_retry_after_price.run_forward_returns_build_from_rows")
@patch("phase33.forward_retry_after_price.report_forward_metric_truth_audit")
@patch("phase33.forward_retry_after_price.get_supabase_client")
def test_forward_retry_skips_without_errors(
    mock_cli: MagicMock,
    mock_truth: MagicMock,
    mock_build: MagicMock,
) -> None:
    from phase33.forward_retry_after_price import (
        run_forward_return_retry_after_price_repair,
    )

    mock_cli.return_value = MagicMock()
    mock_truth.return_value = {"symbol_cleared_from_missing_excess_queue_count": 0}
    b = _minimal_phase32_bundle()
    b["forward_return_backfill_phase31_touched"]["forward_build"] = {
        "error_sample": []
    }
    settings = MagicMock()
    out = run_forward_return_retry_after_price_repair(
        settings, universe_name="u", phase32_bundle=b, panel_limit=50
    )
    assert out.get("skipped") is True
    mock_build.assert_not_called()
