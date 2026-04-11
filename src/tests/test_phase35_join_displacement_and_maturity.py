"""Phase 35 — displacement, join gaps, refresh skip, maturity schedule, review."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from phase35.join_displacement import (
    classify_displacement_for_validation_panel,
    export_forward_validation_join_displacement,
)
from phase35.matured_window_schedule import report_matured_window_schedule_for_forward
from phase35.orchestrator import run_phase35_join_displacement_and_maturity
from phase35.review import (
    write_phase35_join_displacement_and_maturity_bundle_json,
    write_phase35_join_displacement_and_maturity_review_md,
)
from phase35.state_change_refresh import run_state_change_join_refresh_after_phase34
from phase34.price_backfill import run_bounded_price_ingest_for_propagation_missing_windows
from research_validation.metrics import state_change_rows_by_cik_sorted


def _by_cik_from_rows(rows: list[dict]) -> dict:
    return state_change_rows_by_cik_sorted(rows)


def test_displacement_joined_when_score_present() -> None:
    rows = [
        {
            "cik": "1",
            "as_of_date": "2024-01-15",
            "state_change_score_v1": 0.3,
        }
    ]
    by_cik = _by_cik_from_rows(rows)
    panel = {
        "cik": "0000000001",
        "symbol": "ZZ",
        "accession_no": "a",
        "factor_version": "v1",
        "signal_available_date": "2024-06-01",
        "excess_return_1q": 0.02,
    }
    out = classify_displacement_for_validation_panel(panel, by_cik=by_cik)
    assert out["displacement_bucket"] == "included_in_joined_recipe_substrate"
    assert out["join_seam_bucket"] == "joined_now"


def test_displacement_no_state_change_signal_before_first_as_of() -> None:
    rows = [
        {
            "cik": "1",
            "as_of_date": "2024-06-01",
            "state_change_score_v1": 0.1,
        }
    ]
    by_cik = _by_cik_from_rows(rows)
    panel = {
        "cik": "1",
        "symbol": "ZZ",
        "signal_available_date": "2024-01-01",
        "excess_return_1q": 0.02,
    }
    out = classify_displacement_for_validation_panel(panel, by_cik=by_cik)
    assert out["displacement_bucket"] == "excluded_no_state_change_join"
    assert out["join_seam_bucket"] == "state_change_built_but_join_key_mismatch"


def test_displacement_cik_absent() -> None:
    by_cik: dict = {}
    panel = {
        "cik": "99",
        "symbol": "ZZ",
        "signal_available_date": "2024-06-01",
        "excess_return_1q": 0.02,
    }
    out = classify_displacement_for_validation_panel(panel, by_cik=by_cik)
    assert out["displacement_bucket"] == "excluded_no_state_change_join"
    assert out["join_seam_bucket"] == "state_change_not_built_for_row"


@patch("phase34.price_backfill.run_market_prices_ingest_for_symbols")
def test_price_ingest_only_missing_window(mock_ing: MagicMock) -> None:
    mock_ing.return_value = {"status": "completed"}
    client = MagicMock()
    settings = MagicMock()
    gap = {
        "rows": [
            {
                "symbol": "A",
                "signal_available_date": "2020-06-01",
                "price_gap": {"classification": "lookahead_window_not_matured"},
            },
            {
                "symbol": "B",
                "signal_available_date": "2020-06-01",
                "price_gap": {
                    "classification": "missing_market_prices_daily_window"
                },
            },
        ]
    }
    with patch(
        "phase34.price_backfill.dbrec.fetch_silver_prices_for_symbol_range",
        return_value=[{"x": 1}],
    ):
        out = run_bounded_price_ingest_for_propagation_missing_windows(
            settings, client, propagation_gap_report=gap
        )
    assert out["ingest_attempted"] is True
    assert mock_ing.call_args[1]["symbols"] == ["B"]


def test_export_displacement(tmp_path: Path) -> None:
    p = tmp_path / "d.json"
    export_forward_validation_join_displacement({"ok": True}, out_json=str(p))
    assert json.loads(p.read_text(encoding="utf-8"))["ok"] is True


@patch("phase35.state_change_refresh.run_state_change")
@patch("phase35.state_change_refresh.collect_phase33_substrate_snapshot")
@patch("phase35.state_change_refresh.report_forward_validation_join_displacement")
@patch("phase35.state_change_refresh.report_state_change_join_gaps_after_phase34")
@patch("phase35.state_change_refresh.get_supabase_client")
def test_state_change_refresh_skips_without_repairable(
    mock_cli: MagicMock,
    mock_gaps: MagicMock,
    mock_disp: MagicMock,
    mock_snap: MagicMock,
    mock_sc: MagicMock,
) -> None:
    mock_cli.return_value = MagicMock()
    mock_gaps.return_value = {
        "rows": [
            {
                "join_seam_bucket": "state_change_built_but_join_key_mismatch",
                "reference_from_phase34": {"cik": "1"},
            }
        ]
    }
    snap = {
        "joined_recipe_substrate_row_count": 1,
        "exclusion_distribution": {"no_state_change_join": 5},
    }
    mock_snap.side_effect = [snap, snap]
    mock_disp.return_value = {"displacement_counts": {}}
    settings = MagicMock()
    out = run_state_change_join_refresh_after_phase34(
        settings,
        universe_name="u",
        phase34_bundle={"propagation_gap_final": {"rows": []}},
    )
    assert out.get("skipped") is True
    mock_sc.assert_not_called()


@patch("phase35.matured_window_schedule.classify_price_gap_for_forward_row")
def test_matured_schedule_reports_immature(mock_cls: MagicMock) -> None:
    mock_cls.return_value = {
        "classification": "lookahead_window_not_matured",
        "detail": "x",
        "sessions_on_or_after_signal": 10,
    }
    client = MagicMock()
    bundle = {
        "propagation_gap_final": {
            "rows": [
                {
                    "classification": "forward_not_present_window_not_matured",
                    "symbol": "MU",
                    "signal_available_date": "2026-03-19",
                }
            ]
        }
    }
    out = report_matured_window_schedule_for_forward(
        client, phase34_bundle=bundle, expected_symbols=("MU",)
    )
    assert out["still_not_matured_count"] >= 1
    assert out["matured_eligible_now_count"] == 0


def test_phase35_review_write(tmp_path: Path) -> None:
    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 2,
            "exclusion_distribution": {"no_state_change_join": 3},
        },
        "after": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 1,
            "exclusion_distribution": {"no_state_change_join": 1},
        },
        "forward_validation_join_displacement_initial": {
            "hypothesis_phase34_excess_to_no_state_change_join": {
                "supported_by_counts": True,
                "included_in_joined_recipe_substrate": 0,
                "excluded_no_state_change_join": 23,
                "excluded_other_reason": 0,
            }
        },
        "closeout_summary": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 1,
            "missing_validation_symbol_count": 0,
            "missing_quarter_snapshot_for_cik": 0,
            "factor_panel_missing_for_resolved_cik": 0,
            "no_state_change_join": 1,
            "validation_excess_filled_now_count": 23,
            "symbol_cleared_from_missing_excess_queue_count": 23,
            "joined_recipe_unlocked_now_count": 1,
            "no_state_change_join_cleared_count": 2,
            "displacement_synchronized_set_initial": {},
            "displacement_synchronized_set_final": {},
            "matured_eligible_now_count": 0,
            "still_not_matured_count": 7,
            "matured_forward_retry_success_count": 0,
            "price_coverage_repaired_now_count": 0,
            "gis_outcome": "blocked",
            "phase36": {"phase36_recommendation": "x", "rationale": "y"},
        },
        "phase36": {"phase36_recommendation": "x", "rationale": "y"},
    }
    md = tmp_path / "r.md"
    bj = tmp_path / "b.json"
    write_phase35_join_displacement_and_maturity_review_md(str(md), bundle=bundle)
    write_phase35_join_displacement_and_maturity_bundle_json(str(bj), bundle=bundle)
    assert "Phase 35" in md.read_text(encoding="utf-8")
    assert json.loads(bj.read_text(encoding="utf-8"))["closeout_summary"][
        "joined_recipe_unlocked_now_count"
    ] == 1


@patch("phase35.orchestrator.inspect_gis_raw_present_no_silver_deterministic")
@patch("phase35.orchestrator.report_forward_validation_join_displacement")
@patch("phase35.orchestrator.run_state_change_join_refresh_after_phase34")
@patch("phase35.orchestrator.run_bounded_price_ingest_for_propagation_missing_windows")
@patch("phase35.orchestrator.run_matured_window_forward_retry_for_phase34_immature")
@patch("phase35.orchestrator.report_matured_window_schedule_for_forward")
@patch("phase35.orchestrator.report_state_change_join_gaps_after_phase34")
@patch("phase35.orchestrator.collect_phase33_substrate_snapshot")
@patch("phase35.orchestrator.get_supabase_client")
@patch("phase35.orchestrator.load_phase34_bundle")
def test_orchestrator_smoke(
    mock_lb: MagicMock,
    mock_cli: MagicMock,
    mock_snap: MagicMock,
    mock_gaps: MagicMock,
    mock_mws: MagicMock,
    mock_mwr: MagicMock,
    mock_pb: MagicMock,
    mock_ref: MagicMock,
    mock_disp: MagicMock,
    mock_gis: MagicMock,
) -> None:
    mock_lb.return_value = {
        "propagation_gap_final": {"rows": []},
        "closeout_summary": {},
    }
    mock_cli.return_value = MagicMock()
    snap = {
        "joined_recipe_substrate_row_count": 10,
        "thin_input_share": 1.0,
        "missing_excess_return_1q": 5,
        "missing_validation_symbol_count": 0,
        "missing_quarter_snapshot_for_cik": 0,
        "factor_panel_missing_for_resolved_cik": 0,
        "exclusion_distribution": {"no_state_change_join": 2},
    }
    mock_snap.side_effect = [snap, snap]
    hyp = {
        "supported_by_counts": False,
        "included_in_joined_recipe_substrate": 1,
        "excluded_no_state_change_join": 2,
    }

    def _disp_side(*_a: object, **_k: object) -> dict:
        return {
            "hypothesis_phase34_excess_to_no_state_change_join": hyp,
            "displacement_counts": {},
        }

    mock_disp.side_effect = _disp_side
    mock_gaps.return_value = {"rows": []}
    mock_mws.return_value = {"matured_eligible_now_count": 0}
    mock_mwr.return_value = {"matured_forward_retry_success_count": 0}
    mock_pb.return_value = {"price_coverage_repaired_now_count": 0}
    mock_ref.return_value = {"skipped": True}
    mock_gis.return_value = {"outcome": "ok", "blocked_reason": None}

    settings = MagicMock()
    out = run_phase35_join_displacement_and_maturity(
        settings,
        universe_name="u",
        phase34_bundle_path="/tmp/x.json",
    )
    assert out["ok"] is True
    assert "closeout_summary" in out
