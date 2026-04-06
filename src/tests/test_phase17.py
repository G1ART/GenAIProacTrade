from __future__ import annotations

import inspect
import uuid
from collections import Counter
from unittest.mock import MagicMock, patch

import state_change.runner as sc_runner
from main import build_parser
from public_depth.constants import UPLIFT_NUMERIC_KEYS
from public_depth.diagnostics import compute_substrate_coverage
from public_depth.readiness import build_research_readiness_summary
from public_depth.uplift import compute_uplift_metrics
from research_registry import promotion_rules


def test_runner_does_not_reference_public_depth() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_depth" not in src


def test_promotion_rules_guard_includes_public_depth() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


@patch("public_depth.diagnostics.dbrec")
def test_coverage_diagnostics_bounded_keys(mock_dbrec: MagicMock) -> None:
    mock_dbrec.fetch_max_as_of_universe.return_value = "2024-06-30"
    mock_dbrec.fetch_symbols_universe_as_of.return_value = ["AAPL", "MSFT"]
    mock_dbrec.fetch_public_core_cycle_quality_runs_for_universe.return_value = [
        {"quality_class": "thin_input"},
        {"quality_class": "strong"},
    ]
    mock_dbrec.fetch_cik_map_for_tickers.return_value = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
    }
    mock_dbrec.fetch_issuer_quarter_factor_panels_for_ciks.return_value = {}
    mock_dbrec.fetch_latest_state_change_run_id.return_value = None
    mock_dbrec.fetch_state_change_scores_for_run.return_value = []
    mock_dbrec.fetch_factor_market_validation_panels_for_symbols.return_value = []

    client = MagicMock()
    metrics, excl = compute_substrate_coverage(client, universe_name="test_uni")
    required = {
        "joined_recipe_substrate_row_count",
        "validation_join_row_count",
        "validation_panel_row_count",
        "thin_input_share",
        "strong_share",
        "usable_with_gaps_share",
        "degraded_share",
        "dominant_exclusion_reasons",
        "n_issuer_universe",
    }
    assert required <= set(metrics.keys())
    assert isinstance(excl, dict)


def test_uplift_computes_deltas() -> None:
    before = {k: 10 for k in UPLIFT_NUMERIC_KEYS}
    after = {k: 15 for k in UPLIFT_NUMERIC_KEYS}
    before["thin_input_share"] = 0.6
    after["thin_input_share"] = 0.4
    before["strong_share"] = 0.1
    after["strong_share"] = 0.2
    u = compute_uplift_metrics(before, after)
    assert u["deltas"]["joined_recipe_substrate_row_count"] == 5
    assert u["thin_input_improved"] is True
    assert u["joined_substrate_improved"] is True


def test_exclusion_ranking_deterministic() -> None:
    import public_depth.diagnostics as diag

    c = Counter()
    c["zebra"] = 2
    c["apple"] = 2
    c["solo"] = 5
    ranked = diag._dominant_exclusions(c)
    assert [x["reason"] for x in ranked] == ["solo", "apple", "zebra"]


@patch("public_depth.readiness.compute_substrate_coverage")
@patch("public_depth.readiness.dbrec.fetch_research_program")
def test_research_readiness_reflects_substrate(
    mock_fetch_prog: MagicMock, mock_cov: MagicMock
) -> None:
    pid = str(uuid.uuid4())
    mock_fetch_prog.return_value = {
        "universe_name": "U1",
        "linked_quality_context_json": {},
    }
    mock_cov.return_value = (
        {
            "joined_recipe_substrate_row_count": 200,
            "thin_input_share": 0.2,
        },
        {},
    )
    out = build_research_readiness_summary(MagicMock(), program_id=pid)
    assert out["ok"] is True
    assert out["recommend_rerun_phase_15_16"] is True

    mock_cov.return_value = (
        {"joined_recipe_substrate_row_count": 5, "thin_input_share": 0.9},
        {},
    )
    out2 = build_research_readiness_summary(MagicMock(), program_id=pid)
    assert out2["recommend_rerun_phase_15_16"] is False


def test_phase17_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    assert "list-universe-names" in names
    assert "run-public-depth-expansion" in names
    assert "report-public-depth-coverage" in names
    assert "report-quality-uplift" in names
    assert "report-research-readiness" in names
    assert "export-public-depth-brief" in names
