"""factor_validation summary row → Metis gate summary (no DB)."""

from __future__ import annotations

from metis_brain.factor_validation_gate_adapter_v0 import build_metis_gate_summary_from_factor_summary_row
from metis_brain.validation_bridge_v0 import promotion_gate_from_validation_summary


def _base_row(**over: object) -> dict:
    r = {
        "run_id": "run-test-1",
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "sample_count": 200,
        "valid_factor_count": 40,
        "spearman_rank_corr": 0.12,
        "summary_json": {},
    }
    r.update(over)
    return r


def test_coverage_and_spearman_monotonicity() -> None:
    s = build_metis_gate_summary_from_factor_summary_row(_base_row(), quantiles=None, return_basis="raw")
    assert s["coverage_pass"] is True
    assert s["monotonicity_pass"] is True
    assert s["pit_pass"] is False


def test_pit_certified_from_summary_json() -> None:
    s = build_metis_gate_summary_from_factor_summary_row(
        _base_row(summary_json={"pit_certified": True}),
        quantiles=None,
        return_basis="raw",
    )
    assert s["pit_pass"] is True


def test_flat_quantiles_fail_monotonicity() -> None:
    quants = [
        {"quantile_index": 0, "avg_raw_return": 0.02},
        {"quantile_index": 2, "avg_raw_return": 0.02},
        {"quantile_index": 4, "avg_raw_return": 0.02},
    ]
    s = build_metis_gate_summary_from_factor_summary_row(_base_row(), quantiles=quants, return_basis="raw")
    assert s["monotonicity_pass"] is False


def test_low_pair_count_fails_coverage() -> None:
    s = build_metis_gate_summary_from_factor_summary_row(
        _base_row(sample_count=200, valid_factor_count=10),
        quantiles=None,
        return_basis="raw",
    )
    assert s["coverage_pass"] is False


def test_end_to_end_promotion_gate_record() -> None:
    s = build_metis_gate_summary_from_factor_summary_row(
        _base_row(summary_json={"pit_certified": True}),
        quantiles=None,
        return_basis="excess",
    )
    g = promotion_gate_from_validation_summary(
        artifact_id="art_demo",
        evaluation_run_id="run-test-1",
        summary=s,
    )
    assert g.artifact_id == "art_demo"
    assert g.evaluation_run_id == "run-test-1"
    assert g.pit_pass and g.coverage_pass and g.monotonicity_pass
