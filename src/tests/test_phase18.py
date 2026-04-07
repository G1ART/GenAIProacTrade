from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock, patch

import state_change.runner as sc_runner
from main import build_parser
from public_buildout.actions import build_action_queue_json
from public_buildout.constants import JOINED_THRESHOLD_PHASE16
from public_buildout.improvement import compute_buildout_improvement_summary
from public_buildout.orchestrator import (
    _select_targets,
    report_buildout_improvement_from_coverage_ids,
)
from public_buildout.revalidation import build_revalidation_trigger
from research_registry import promotion_rules


def test_runner_does_not_reference_public_buildout() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_buildout" not in src


def test_promotion_rules_guard_includes_public_buildout() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


def test_select_targets_sorts_by_count_and_respects_flags() -> None:
    ex = {
        "no_validation_panel_for_symbol": 10,
        "no_state_change_join": 5,
        "missing_excess_return_1q": 20,
    }
    all_t = _select_targets(
        ex,
        attack_validation=True,
        attack_state_change=True,
        attack_forward_returns=True,
    )
    assert all_t[0] == "missing_excess_return_1q"

    v_only = _select_targets(
        ex,
        attack_validation=True,
        attack_state_change=False,
        attack_forward_returns=False,
    )
    assert v_only == ["no_validation_panel_for_symbol"]


def test_action_queue_truncation_and_sort() -> None:
    syms = [f"S{i}" for i in range(600)]
    q = build_action_queue_json(
        {"no_validation_panel_for_symbol": 100, "no_state_change_join": 200},
        {"no_validation_panel_for_symbol": syms, "no_state_change_join": ["A"]},
    )
    assert q[0]["reason"] == "no_state_change_join"
    row = next(r for r in q if r["reason"] == "no_validation_panel_for_symbol")
    assert len(row["symbols_sample"]) == 500
    assert row["symbols_truncated"] is True


def test_buildout_improvement_summary_exclusion_deltas() -> None:
    be = {"no_validation_panel_for_symbol": 10}
    ae = {"no_validation_panel_for_symbol": 7}
    bm = {"joined_recipe_substrate_row_count": 100, "thin_input_share": 0.6}
    am = {"joined_recipe_substrate_row_count": 110, "thin_input_share": 0.5}
    summ = compute_buildout_improvement_summary(bm, am, be, ae)
    tr = summ["exclusion_improvement"]["tracked"]["no_validation_panel_for_symbol"]
    assert tr["delta"] == -3
    assert tr["reduced"] is True


@patch("public_buildout.revalidation.compute_substrate_coverage")
@patch("public_buildout.revalidation.dbrec.fetch_research_program")
def test_revalidation_trigger_phase15_16_booleans(
    mock_fetch_prog: MagicMock, mock_cov: MagicMock
) -> None:
    pid = str(uuid.uuid4())
    mock_fetch_prog.return_value = {
        "universe_name": "U1",
        "linked_quality_context_json": {},
    }
    mock_cov.return_value = (
        {
            "joined_recipe_substrate_row_count": JOINED_THRESHOLD_PHASE16 + 1,
            "thin_input_share": 0.4,
        },
        {},
    )
    out = build_revalidation_trigger(MagicMock(), program_id=pid)
    assert out["ok"] is True
    assert out["recommend_rerun_phase15"] is True
    assert out["recommend_rerun_phase16"] is True

    mock_cov.return_value = (
        {
            "joined_recipe_substrate_row_count": JOINED_THRESHOLD_PHASE16 + 1000,
            "thin_input_share": 0.5,
        },
        {},
    )
    out2 = build_revalidation_trigger(MagicMock(), program_id=pid)
    assert out2["recommend_rerun_phase16"] is False
    assert out2["recommend_rerun_phase15"] is True


def test_phase18_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    for cmd in (
        "smoke-phase18-public-buildout",
        "report-public-exclusion-actions",
        "run-targeted-public-buildout",
        "report-buildout-improvement",
        "report-revalidation-trigger",
        "export-buildout-brief",
    ):
        assert cmd in names


@patch("public_buildout.orchestrator.dbrec.fetch_public_depth_coverage_report")
def test_buildout_improvement_not_found_includes_found_flags(
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.side_effect = [None, {"metrics_json": {}, "exclusion_distribution_json": {}}]
    out = report_buildout_improvement_from_coverage_ids(
        MagicMock(),
        before_report_id="00000000-0000-4000-8000-000000000001",
        after_report_id="00000000-0000-4000-8000-000000000002",
    )
    assert out["ok"] is False
    assert out["error"] == "coverage_report_not_found"
    assert out["before_found"] is False
    assert out["after_found"] is True


def test_report_buildout_improvement_parser_accepts_latest_pair() -> None:
    p = build_parser()
    ns = p.parse_args(
        [
            "report-buildout-improvement",
            "--universe",
            "sp500_current",
            "--from-latest-pair",
        ]
    )
    assert ns.universe == "sp500_current"
    assert ns.from_latest_pair is True
    assert ns.before_report_id is None
    assert ns.after_report_id is None

