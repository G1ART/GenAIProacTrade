"""Phase 26: thin-input drivers, repair audit, exports, sensitivity, boundaries."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import public_core.quality as qc_mod
from thin_input_root_cause.decompose import _joined_row_driver_bucket, report_thin_input_drivers
from thin_input_root_cause.effectiveness import report_validation_repair_effectiveness
from thin_input_root_cause.exports import export_unresolved_validation_symbols
from thin_input_root_cause.phase27 import PHASE27_RERUN_15_16, classify_phase27_next_move
from thin_input_root_cause.policy_trace import (
    report_quality_threshold_sensitivity,
    trace_thin_input_rule,
)


def test_joined_row_driver_bucket_clean_vs_flags() -> None:
    assert (
        _joined_row_driver_bucket({"panel_json": {}})
        == "joined_panel_json_clean_no_quality_flags"
    )
    assert (
        _joined_row_driver_bucket(
            {"panel_json": {"quality_flags": ["missing_forward_return_1m"]}}
        )
        == "joined_but_forward_quality_flags_present"
    )


def test_trace_thin_input_rule_insufficient_branch() -> None:
    m = {
        "insufficient_data_fraction": 0.8,
        "gating_high_missingness_fraction": 0.1,
        "watchlist_selected": 0,
        "casebook_entries_created": 0,
        "candidates_scanned": 100,
        "harness_error_rate": 0.0,
        "stage_status_by_name": {},
    }
    tr = trace_thin_input_rule(cycle_ok=True, scanner_failed=False, metrics=m)
    assert tr["quality_class"] == "thin_input"
    assert any("0.75" in str(x) for x in tr["thin_classification_reasons"])


def test_report_thin_input_drivers_joined_samples() -> None:
    client = MagicMock()

    def _cov(*_a, **kwargs):
        j = kwargs.get("joined_panels_out")
        if j is not None:
            j.append(
                {
                    "symbol": "AAA",
                    "cik": "1",
                    "accession_no": "a",
                    "factor_version": "v1",
                    "signal_available_date": "2023-01-01",
                    "excess_return_1q": 0.01,
                    "state_change_score_v1": 0.5,
                    "state_change_as_of_date": "2022-12-01",
                    "panel_json": {},
                }
            )
        return (
            {
                "universe_name": "u1",
                "thin_input_share": 1.0,
                "joined_recipe_substrate_row_count": 1,
                "dominant_exclusion_reasons": [],
            },
            {"no_validation_panel_for_symbol": 5},
        )

    with (
        patch(
            "thin_input_root_cause.decompose.compute_substrate_coverage",
            side_effect=_cov,
        ),
        patch(
            "thin_input_root_cause.decompose.resolve_program_id",
            return_value={"ok": False, "error": "test"},
        ),
        patch(
            "thin_input_root_cause.decompose.build_revalidation_trigger",
            return_value={"ok": False},
        ),
        patch(
            "thin_input_root_cause.decompose.dbrec.fetch_public_core_cycle_quality_runs_for_universe",
            return_value=[
                {
                    "id": "q1",
                    "quality_class": "thin_input",
                    "cycle_finished_ok": True,
                    "scanner_failed": False,
                    "metrics_json": {
                        "insufficient_data_fraction": 0.8,
                        "gating_high_missingness_fraction": 0.1,
                        "watchlist_selected": 0,
                        "casebook_entries_created": 0,
                        "candidates_scanned": 10,
                    },
                }
            ],
        ),
    ):
        out = report_thin_input_drivers(
            client, universe_name="u1", program_id_raw=None, panel_limit=10
        )
    assert out["joined_substrate_row_count"] == 1
    assert out["cycle_thin_driver_counts"].get("thin_insufficient_ge_075", 0) >= 1


def test_validation_repair_effectiveness_zero_targets() -> None:
    client = MagicMock()
    with (
        patch(
            "thin_input_root_cause.effectiveness.collect_panels_for_validation_repair",
            return_value=([], {"panel_rows": 0, "diagnosis_summary": {}}),
        ),
        patch(
            "thin_input_root_cause.effectiveness.compute_substrate_coverage",
            return_value=({}, {"no_validation_panel_for_symbol": 10}),
        ),
        patch(
            "thin_input_root_cause.effectiveness._substrate_closure_ingest_runs",
            return_value=[],
        ),
    ):
        out = report_validation_repair_effectiveness(
            client, universe_name="u1", panel_limit=100
        )
    assert out["likely_no_op"] is True
    assert out["targets_identified_panel_rows"] == 0


def test_export_unresolved_validation_json_shape(tmp_path: Path) -> None:
    client = MagicMock()

    def _cov(*_a, **kwargs):
        q = kwargs.get("symbol_queues_out")
        if q is not None:
            q.clear()
            q["no_validation_panel_for_symbol"] = ["ZZZ"]
        return ({}, {})

    with patch(
        "thin_input_root_cause.exports.compute_substrate_coverage",
        side_effect=_cov,
    ):
        p = tmp_path / "x.json"
        meta = export_unresolved_validation_symbols(
            client, universe_name="u1", panel_limit=10, out_path=p, fmt="json"
        )
    assert meta["count"] == 1
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data[0]["symbol"] == "ZZZ"
    assert data[0]["reason"] == "no_validation_panel_for_symbol"


def test_threshold_sensitivity_does_not_mutate_public_core_constants() -> None:
    before = qc_mod.THIN_INPUT_INSUFFICIENT_FRAC
    m = {
        "insufficient_data_fraction": 0.82,
        "gating_high_missingness_fraction": 0.4,
        "watchlist_selected": 0,
        "casebook_entries_created": 0,
        "candidates_scanned": 50,
        "harness_error_rate": 0.0,
        "harness_error_count": 0,
        "harness_inputs_built": 0,
        "memos_touched": 0,
        "stage_status_by_name": {},
    }
    out = report_quality_threshold_sensitivity(
        cycle_ok=True, scanner_failed=False, metrics=m
    )
    assert out["no_automatic_threshold_mutation"] is True
    assert qc_mod.THIN_INPUT_INSUFFICIENT_FRAC == before


def test_phase27_rerun_when_gates_open() -> None:
    r = classify_phase27_next_move(
        recommend_rerun_phase15=True,
        recommend_rerun_phase16=False,
        primary_blocker_category="data_absence",
        generic_substrate_sprint_likely_wasteful=True,
        thin_input_share=1.0,
        joined_substrate_rows=200,
    )
    assert r["phase27_recommendation"] == PHASE27_RERUN_15_16


def test_thin_input_root_cause_no_premium_or_production_wiring() -> None:
    forbidden = (
        "hypothesis_registry",
        "research_engine",
        "validation_campaign",
        "open_targeted_premium_discovery",
    )
    for mod_name in (
        "thin_input_root_cause",
        "thin_input_root_cause.decompose",
        "thin_input_root_cause.effectiveness",
        "thin_input_root_cause.exports",
        "thin_input_root_cause.policy_trace",
        "thin_input_root_cause.review",
        "thin_input_root_cause.phase27",
    ):
        m = importlib.import_module(mod_name)
        src = inspect.getsource(m)
        for tok in forbidden:
            assert tok not in src, f"{mod_name} must not reference {tok}"
