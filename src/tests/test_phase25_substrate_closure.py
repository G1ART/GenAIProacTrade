"""Phase 25: substrate gap diagnosis, repair deltas, scoreboard, gates, boundaries."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_validation.metrics import pick_state_change_at_or_before_signal
from substrate_closure import diagnose as sc_diag
from substrate_closure.review import (
    format_rerun_gate_report,
    recommend_phase26_from_gates,
    write_substrate_closure_review_md,
)


def test_validation_panel_gap_buckets_build_omission() -> None:
    client = MagicMock()
    metrics = {
        "as_of_date": "2024-01-01",
        "universe_name": "sp500_current",
    }

    def _cov(*_a, **kwargs):
        q = kwargs.get("symbol_queues_out")
        if q is not None:
            q.clear()
            q["no_validation_panel_for_symbol"] = ["FOO"]
        return metrics, {}

    with (
        patch.object(sc_diag, "compute_substrate_coverage", side_effect=_cov),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_symbols_universe_as_of",
            return_value=["FOO"],
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_cik_map_for_tickers",
            return_value={"FOO": "1"},
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_issuer_quarter_factor_panels_for_ciks",
            return_value={("1", "acc", "v1"): {"cik": "1", "accession_no": "acc", "factor_version": "v1"}},
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_ticker_for_cik",
            return_value="FOO",
        ),
        patch.object(sc_diag, "_fetch_validation_rows_for_ciks", return_value=[]),
    ):
        out = sc_diag.report_validation_panel_coverage_gaps(
            client, universe_name="sp500_current", panel_limit=100
        )
    assert out["ok"] is True
    assert "validation_panel_build_omission_for_cik" in out["reason_buckets"]
    assert "FOO" in out["reason_buckets"]["validation_panel_build_omission_for_cik"]


def test_forward_return_gap_no_forward_row() -> None:
    client = MagicMock()
    metrics = {"as_of_date": "2024-01-01"}
    panel = {
        "symbol": "FOO",
        "cik": "0000000001",
        "accession_no": "a1",
        "signal_available_date": "2023-06-15",
        "excess_return_1q": None,
    }

    def _cov(*_a, **kwargs):
        q = kwargs.get("symbol_queues_out")
        if q is not None:
            q.clear()
            q["missing_excess_return_1q"] = ["FOO"]
        return metrics, {}

    with (
        patch.object(sc_diag, "compute_substrate_coverage", side_effect=_cov),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_factor_market_validation_panels_for_symbols",
            return_value=[panel],
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_forward_return_for_signal",
            return_value=None,
        ),
    ):
        out = sc_diag.report_forward_return_gaps(
            client, universe_name="sp500_current", panel_limit=100
        )
    assert out["row_reason_counts"].get("no_forward_row_next_quarter", 0) >= 1


def test_state_change_join_gap_no_scores_for_cik() -> None:
    client = MagicMock()
    metrics = {
        "as_of_date": "2024-01-01",
        "state_change_run_id": "run-1",
    }
    panel = {
        "symbol": "FOO",
        "cik": "0000000001",
        "accession_no": "a1",
        "signal_available_date": "2023-06-15",
        "excess_return_1q": 0.01,
    }

    def _cov(*_a, **kwargs):
        q = kwargs.get("symbol_queues_out")
        if q is not None:
            q.clear()
            q["no_state_change_join"] = ["FOO"]
        return metrics, {}

    with (
        patch.object(sc_diag, "compute_substrate_coverage", side_effect=_cov),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_factor_market_validation_panels_for_symbols",
            return_value=[panel],
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_state_change_scores_for_run",
            return_value=[],
        ),
    ):
        out = sc_diag.report_state_change_join_gaps(
            client, universe_name="sp500_current", panel_limit=100
        )
    assert out["row_reason_counts"].get("no_state_change_scores_for_cik_in_latest_run", 0) >= 1


def test_targeted_repair_reduces_exclusion_count() -> None:
    from substrate_closure.repair import run_validation_panel_coverage_repair

    settings = object()
    before_ex = {"no_validation_panel_for_symbol": 5, "missing_excess_return_1q": 0}
    after_ex = {"no_validation_panel_for_symbol": 2, "missing_excess_return_1q": 0}
    gap_reports = [
        {
            "missing_symbol_count": 5,
            "reason_bucket_counts": {"validation_panel_build_omission_for_cik": 1},
            "reason_buckets": {"validation_panel_build_omission_for_cik": ["A"]},
            "metrics": {"as_of_date": "2024-01-01"},
            "exclusion_distribution": dict(before_ex),
        },
        {
            "missing_symbol_count": 2,
            "reason_bucket_counts": {},
            "reason_buckets": {},
            "metrics": {"as_of_date": "2024-01-01"},
            "exclusion_distribution": dict(after_ex),
        },
    ]

    def _next_gap(*_a, **_k):
        return gap_reports.pop(0)

    with (
        patch(
            "substrate_closure.repair.report_validation_panel_coverage_gaps",
            side_effect=_next_gap,
        ),
        patch(
            "substrate_closure.repair.collect_panels_for_validation_repair",
            return_value=([], {"target_cik_count": 0}),
        ),
        patch(
            "substrate_closure.repair.run_validation_panel_build_from_rows",
            return_value={"skipped": False, "rows_upserted": 3},
        ),
        patch("db.client.get_supabase_client", return_value=MagicMock()),
    ):
        out = run_validation_panel_coverage_repair(
            settings, universe_name="sp500_current", panel_limit=100
        )
    assert out["before"]["missing_validation_panel_symbol_count"] == 5
    assert out["after"]["missing_validation_panel_symbol_count"] == 2


def test_scoreboard_before_after_math_in_markdown(tmp_path: Path) -> None:
    before = {
        "metrics": {
            "thin_input_share": 1.0,
            "joined_recipe_substrate_row_count": 10,
            "n_issuer_with_validation_panel_symbol": 50,
            "n_issuer_with_next_quarter_excess": 40,
            "n_issuer_with_state_change_cik": 45,
        },
        "exclusion_distribution": {
            "no_validation_panel_for_symbol": 100,
            "missing_excess_return_1q": 30,
            "no_state_change_join": 5,
        },
        "rerun_readiness": {
            "ok": True,
            "recommend_rerun_phase15": False,
            "recommend_rerun_phase16": False,
        },
    }
    after = {
        "metrics": {
            "thin_input_share": 0.8,
            "joined_recipe_substrate_row_count": 20,
            "n_issuer_with_validation_panel_symbol": 60,
            "n_issuer_with_next_quarter_excess": 50,
            "n_issuer_with_state_change_cik": 48,
        },
        "exclusion_distribution": {
            "no_validation_panel_for_symbol": 80,
            "missing_excess_return_1q": 25,
            "no_state_change_join": 4,
        },
        "rerun_readiness": {
            "ok": True,
            "recommend_rerun_phase15": True,
            "recommend_rerun_phase16": False,
        },
    }
    p = tmp_path / "substrate_closure_review.md"
    write_substrate_closure_review_md(
        path=p,
        universe_name="sp500_current",
        before=before,
        after=after,
        program_id="prog-1",
        phase26_recommendation="test-rec",
    )
    text = p.read_text(encoding="utf-8")
    assert "| thin_input_share |" in text
    assert "100" in text and "80" in text
    assert "recommend_rerun_phase15: `True`" in text


def test_rerun_gate_state_in_report_strings() -> None:
    opened = {
        "ok": True,
        "recommend_rerun_phase15": True,
        "recommend_rerun_phase16": True,
        "substrate_snapshot": {"joined_recipe_substrate_row_count": 300, "thin_input_share": 0.1},
        "thresholds": {},
    }
    s = format_rerun_gate_report(opened)
    assert "opened" in s
    rec = recommend_phase26_from_gates(opened)
    assert "재실행" in rec or "phase15" in rec.lower()


def test_pick_state_change_pit_no_future_leak() -> None:
    row_past = {"state_change_score_v1": 0.2, "as_of_date": "2020-01-01"}
    row_future = {"state_change_score_v1": 0.9, "as_of_date": "2025-01-01"}
    by_cik = {
        "0000000001": [
            ("2020-01-01", row_past),
            ("2025-01-01", row_future),
        ]
    }
    picked = pick_state_change_at_or_before_signal(
        by_cik, cik="1", signal_date="2021-06-01"
    )
    assert picked == row_past


def test_substrate_closure_package_does_not_import_research_pipeline_wiring() -> None:
    """프로덕션 스코어링 경계: substrate_closure가 레지스트리/엔진 직접 연결을 끌어오지 않는다."""
    forbidden = (
        "hypothesis_registry",
        "research_engine",
        "validation_campaign",
        "public_repair_campaign",
    )
    for mod_name in (
        "substrate_closure",
        "substrate_closure.diagnose",
        "substrate_closure.repair",
        "substrate_closure.snapshot",
        "substrate_closure.review",
    ):
        m = importlib.import_module(mod_name)
        src = inspect.getsource(m)
        for token in forbidden:
            assert token not in src, f"{mod_name} must not reference {token}"


def test_exclusion_counter_not_duplicated_per_symbol_in_diagnostics_contract() -> None:
    """한 심볼당 no_validation_panel_for_symbol 은 행 1회(심볼 집합 크기)로 올라간다."""
    from public_depth.diagnostics import compute_substrate_coverage

    client = MagicMock()
    as_of = "2024-01-02"
    symbols = ["A", "B"]
    panels = [
        {
            "symbol": "A",
            "cik": "0000000001",
            "signal_available_date": "2023-01-01",
            "excess_return_1q": 0.01,
        }
    ]

    with (
        patch(
            "public_depth.diagnostics.dbrec.fetch_max_as_of_universe",
            return_value=as_of,
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_symbols_universe_as_of",
            return_value=symbols,
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_public_core_cycle_quality_runs_for_universe",
            return_value=[],
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_cik_map_for_tickers",
            return_value={"A": "1", "B": "2"},
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_issuer_quarter_factor_panels_for_ciks",
            return_value={},
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_latest_state_change_run_id",
            return_value=None,
        ),
        patch(
            "public_depth.diagnostics.dbrec.fetch_factor_market_validation_panels_for_symbols",
            return_value=panels,
        ),
    ):
        _m, ex = compute_substrate_coverage(
            client, universe_name="sp500_current", panel_limit=100
        )
    assert ex.get("no_validation_panel_for_symbol") == 1


def test_report_validation_panel_coverage_gaps_json_serializable() -> None:
    client = MagicMock()
    with (
        patch.object(
            sc_diag,
            "compute_substrate_coverage",
            return_value=({"as_of_date": None}, {}),
        ),
        patch(
            "substrate_closure.diagnose.dbrec.fetch_symbols_universe_as_of",
            return_value=[],
        ),
    ):
        out = sc_diag.report_validation_panel_coverage_gaps(
            client, universe_name="u", panel_limit=10
        )
    json.dumps(out, default=str)
