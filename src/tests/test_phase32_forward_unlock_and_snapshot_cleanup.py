"""Phase 32 — forward 타깃 선별, 백필, silver/GIS, raw 재시도, 리뷰."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from phase32.forward_return_phase31 import (
    export_forward_return_gap_targets_after_phase31,
    report_forward_return_gap_targets_after_phase31,
)
from phase32.phase31_bundle_io import (
    phase31_downstream_unblocked_ciks,
    phase31_touched_cik_list,
)
from phase32.phase33_recommend import recommend_phase33_after_phase32
from phase32.raw_deferred_retry import _classify_retry_outcome
from phase32.review import (
    write_phase32_forward_unlock_and_snapshot_cleanup_bundle_json,
    write_phase32_forward_unlock_and_snapshot_cleanup_review_md,
)


def test_phase31_bundle_io_touched_order() -> None:
    bundle = {
        "downstream_substrate_retry": {
            "per_cik": [
                {
                    "cik": "0001",
                    "validation_panel": {"skipped": False},
                },
                {"cik": "0002", "validation_panel": {"skipped": True}},
            ]
        },
        "raw_facts_backfill_repair": {
            "repaired_to_raw_present": [{"cik": "0003", "symbol": "ZZZ"}]
        },
    }
    assert phase31_downstream_unblocked_ciks(bundle) == ["0001"]
    assert phase31_touched_cik_list(bundle) == ["0001"]


def test_phase31_bundle_io_fallback_raw_only() -> None:
    bundle = {
        "raw_facts_backfill_repair": {
            "repaired_to_raw_present": [{"cik": "0003"}, {"cik": "0003"}]
        }
    }
    assert phase31_touched_cik_list(bundle) == ["0003"]


def test_classify_retry_outcome_recovered() -> None:
    assert (
        _classify_retry_outcome(
            last_exc=None,
            extract_ok=True,
            cls_after="silver_present_snapshot_materialization_missing",
        )
        == "recovered_on_retry"
    )


def test_classify_retry_outcome_external() -> None:
    assert (
        _classify_retry_outcome(
            last_exc="ConnectionTerminated",
            extract_ok=None,
            cls_after="filing_index_present_no_raw_facts",
        )
        == "persistent_external_failure"
    )


def test_export_forward_return_gap_report_tmp(tmp_path: Path) -> None:
    rep = {"ok": True, "target_entries": []}
    p = tmp_path / "gap.json"
    export_forward_return_gap_targets_after_phase31(rep, out_json=str(p))
    assert json.loads(p.read_text(encoding="utf-8"))["ok"] is True


@patch("phase32.forward_return_phase31.compute_substrate_coverage")
@patch("phase32.forward_return_phase31.dbrec.fetch_factor_market_validation_panels_for_symbols")
@patch("phase32.forward_return_phase31.dbrec.fetch_ticker_for_cik")
def test_report_forward_gap_targets_filters_queue(
    mock_ticker: MagicMock,
    mock_panels: MagicMock,
    mock_cov: MagicMock,
) -> None:
    def _cov_side_effect(
        *args: object, symbol_queues_out: dict | None = None, **kwargs: object
    ) -> tuple[dict, dict]:
        if symbol_queues_out is not None:
            symbol_queues_out["missing_excess_return_1q"] = ["ABCD"]
        return (
            {"joined_recipe_substrate_row_count": 1},
            {"missing_excess_return_1q": 2},
        )

    mock_cov.side_effect = _cov_side_effect
    mock_ticker.return_value = "ABCD"
    mock_panels.return_value = [
        {
            "symbol": "ABCD",
            "cik": "123",
            "accession_no": "a1",
            "signal_available_date": "2020-01-15",
            "excess_return_1q": None,
        }
    ]
    with patch(
        "phase32.forward_return_phase31.dbrec.fetch_forward_return_for_signal",
        return_value=None,
    ):
        bundle = {
            "downstream_substrate_retry": {
                "per_cik": [{"cik": "123", "validation_panel": {"skipped": False}}]
            }
        }
        client = MagicMock()
        out = report_forward_return_gap_targets_after_phase31(
            client,
            bundle=bundle,
            universe_name="u1",
            panel_limit=100,
            max_target_ciks=10,
        )
    mock_cov.assert_called_once()
    assert out["ok"] is True
    assert out["diagnose_bucket_counts"].get("no_forward_row_next_quarter", 0) >= 1


@patch("phase32.forward_return_phase31.run_forward_returns_build_from_rows")
@patch("phase32.forward_return_phase31._collect_factor_panels_for_cik_accession")
@patch("phase32.forward_return_phase31.report_forward_return_gap_targets_after_phase31")
def test_run_forward_backfill_skips_when_no_panels(
    mock_rep: MagicMock,
    mock_collect: MagicMock,
    mock_build: MagicMock,
) -> None:
    from phase32.forward_return_phase31 import (
        run_forward_return_backfill_for_phase31_touched,
    )

    mock_rep.return_value = {
        "target_entries": [
            {
                "cik": "1",
                "symbol": "S",
                "accession_no": "acc",
                "diagnose_bucket": "no_forward_row_next_quarter",
            }
        ]
    }
    mock_collect.return_value = ([], {"panel_rows": 0})
    settings = MagicMock()
    with patch("db.client.get_supabase_client") as m_cli:
        client = MagicMock()
        m_cli.return_value = client
        mock_pfv = MagicMock(side_effect=[[{"excess_return_1q": None, "signal_available_date": "2020-01-01"}], []])
        with patch(
            "phase32.forward_return_phase31.dbrec.fetch_factor_market_validation_panels_for_symbols",
            mock_pfv,
        ):
            with patch(
                "phase32.forward_return_phase31.dbrec.fetch_forward_return_for_signal",
                return_value=None,
            ):
                out = run_forward_return_backfill_for_phase31_touched(
                    settings,
                    bundle={"downstream_substrate_retry": {"per_cik": []}},
                    universe_name="u",
                    panel_limit=50,
                    max_target_ciks=5,
                )
    assert out["forward_build"]["skipped"] is True
    mock_build.assert_not_called()


@patch("phase32.silver_snapshot_cleanup.run_downstream_substrate_cascade_for_ciks")
@patch("phase32.silver_snapshot_cleanup.rebuild_quarter_snapshot_from_db")
@patch("phase32.silver_snapshot_cleanup.find_silver_accession_without_snapshot")
@patch("phase32.silver_snapshot_cleanup.classify_cik_quarter_snapshot_gap")
@patch("phase32.silver_snapshot_cleanup.report_silver_present_snapshot_materialization_targets")
def test_silver_snapshot_repair_runs_rebuild(
    mock_targets: MagicMock,
    mock_cls: MagicMock,
    mock_find: MagicMock,
    mock_reb: MagicMock,
    mock_cascade: MagicMock,
) -> None:
    from phase32.silver_snapshot_cleanup import (
        run_silver_present_snapshot_materialization_repair,
    )

    mock_targets.return_value = {
        "targets": [{"cik": "99", "symbol": "GIS", "class": "silver_present_snapshot_materialization_missing"}],
        "target_count": 1,
    }
    mock_cls.side_effect = [
        "silver_present_snapshot_materialization_missing",
        "unexpected_snapshots_present",
    ]
    mock_find.side_effect = ["acc-1", None]
    mock_reb.return_value = {"ok": True}
    mock_cascade.return_value = {"per_cik": [{"cik": "99"}]}
    settings = MagicMock()
    client = MagicMock()
    out = run_silver_present_snapshot_materialization_repair(
        settings, client, universe_name="u", panel_limit=100, max_cik_repairs=5
    )
    assert mock_reb.call_count == 1
    assert out["snapshot_materialized_now_count"] == 1


@patch("phase32.silver_snapshot_cleanup.run_gis_like_silver_materialization_seam_repair")
def test_gis_repair_delegates(mock_gis: MagicMock) -> None:
    from phase32.silver_snapshot_cleanup import run_gis_raw_present_no_silver_repair

    mock_gis.return_value = {"actions": []}
    settings = MagicMock()
    run_gis_raw_present_no_silver_repair(settings, universe_name="u", panel_limit=50)
    mock_gis.assert_called_once()
    ca = mock_gis.call_args
    assert ca.kwargs.get("max_cik_repairs") == 1


def test_write_phase32_review_and_bundle(tmp_path: Path) -> None:
    bundle = {
        "before": {
            "joined_recipe_substrate_row_count": 1,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 5,
            "missing_validation_symbol_count": 2,
            "missing_quarter_snapshot_for_cik": 3,
            "factor_panel_missing_for_resolved_cik": 4,
            "quarter_snapshot_classification_counts": {"raw_present_no_silver_facts": 1},
        },
        "after": {
            "joined_recipe_substrate_row_count": 2,
            "thin_input_share": 0.9,
            "missing_excess_return_1q": 4,
            "missing_validation_symbol_count": 2,
            "missing_quarter_snapshot_for_cik": 2,
            "factor_panel_missing_for_resolved_cik": 4,
            "quarter_snapshot_classification_counts": {"raw_present_no_silver_facts": 0},
        },
        "forward_return_backfill_phase31_touched": {
            "repaired_to_forward_present": 1,
            "deferred_market_data_gap": 0,
            "blocked_registry_or_time_window_issue": 0,
            "panels_built": 2,
        },
        "silver_present_snapshot_materialization_repair": {
            "snapshot_materialized_now_count": 1,
            "actions": [],
        },
        "gis_raw_present_no_silver_repair": {"actions": []},
        "raw_facts_deferred_retry": {
            "outcome_summary": {
                "recovered_on_retry": 1,
                "persistent_external_failure": 0,
                "persistent_schema_or_mapping_issue": 0,
            }
        },
        "stage_transitions": {
            "phase31_reference": {"validation_unblocked_cik_count_in_phase31": 30},
            "forward_return_unlocked_now_count": 1,
            "quarter_snapshot_materialized_now_count": 1,
            "factor_materialized_now_count": 1,
            "validation_panel_refreshed_count": 1,
            "gis_seam_actions_count": 0,
            "raw_facts_recovered_on_retry_count": 1,
        },
        "phase33": {
            "phase33_recommendation": "continue_bounded_forward_return_and_price_coverage",
            "rationale": "test",
        },
    }
    md = tmp_path / "r.md"
    bj = tmp_path / "b.json"
    write_phase32_forward_unlock_and_snapshot_cleanup_review_md(str(md), bundle=bundle)
    write_phase32_forward_unlock_and_snapshot_cleanup_bundle_json(str(bj), bundle=bundle)
    assert "Phase 32" in md.read_text(encoding="utf-8")
    assert json.loads(bj.read_text(encoding="utf-8"))["phase33"]["rationale"] == "test"


def test_phase33_recommend_forward_branch() -> None:
    before = {"missing_excess_return_1q": 10, "joined_recipe_substrate_row_count": 1, "thin_input_share": 1.0}
    after = dict(before)
    after["missing_excess_return_1q"] = 9
    out = recommend_phase33_after_phase32(
        before=before,
        after=after,
        forward_backfill={"repaired_to_forward_present": 0},
        silver_snapshot_repair={"snapshot_materialized_now_count": 0},
        raw_deferred_retry={"outcome_summary": {}},
    )
    assert "phase33_recommendation" in out


def test_classify_extract_false_schema() -> None:
    assert (
        _classify_retry_outcome(
            last_exc=None,
            extract_ok=False,
            cls_after="filing_index_present_no_raw_facts",
        )
        == "persistent_schema_or_mapping_issue"
    )
