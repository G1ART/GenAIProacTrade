from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock, patch

import pytest

import state_change.runner as sc_runner
from main import build_parser
from public_repair_iteration.depth_iteration import (
    append_public_depth_expansion_to_iteration_series,
    build_public_depth_iteration_ledger,
    export_public_depth_series_brief,
)
from public_repair_iteration.depth_signal import compute_public_depth_operator_signal
from public_repair_iteration.marginal_policy import classify_public_depth_improvement
from public_repair_iteration.service import collect_plateau_snapshots_for_series
from research_registry import promotion_rules


def test_runner_still_no_public_repair_iteration_reference() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_iteration" not in src
    assert "public_repair_campaign" not in src


def test_promotion_boundary_still_closed() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


def test_classify_meaningful_progress_joined() -> None:
    L = {
        "expansion_ok": True,
        "joined_recipe_substrate_row_count_delta": 30,
        "thin_input_share_delta": 0.0,
    }
    assert classify_public_depth_improvement(L) == "meaningful_progress"


def test_classify_meaningful_progress_thin() -> None:
    L = {
        "expansion_ok": True,
        "joined_recipe_substrate_row_count_delta": 0,
        "thin_input_share_delta": -0.05,
    }
    assert classify_public_depth_improvement(L) == "meaningful_progress"


def test_classify_marginal_progress() -> None:
    L = {
        "expansion_ok": True,
        "joined_recipe_substrate_row_count_delta": 5,
        "thin_input_share_delta": -0.01,
    }
    assert classify_public_depth_improvement(L) == "marginal_progress"


def test_classify_no_material_progress() -> None:
    L = {
        "expansion_ok": True,
        "joined_recipe_substrate_row_count_delta": 0,
        "thin_input_share_delta": 0.0,
    }
    assert classify_public_depth_improvement(L) == "no_material_progress"


def test_classify_degraded_joined_drop() -> None:
    L = {
        "expansion_ok": True,
        "joined_recipe_substrate_row_count_delta": -3,
        "thin_input_share_delta": 0.0,
    }
    assert classify_public_depth_improvement(L) == "degraded_or_noisy"


def test_classify_degraded_expansion_failed() -> None:
    L = {"expansion_ok": False, "error_message": "boom"}
    assert classify_public_depth_improvement(L) == "degraded_or_noisy"


def test_classify_degraded_infra_does_not_skip_policy() -> None:
    """Infra-style errors on failed expansion are still degraded (ledger), excluded from plateau."""
    L = {"expansion_ok": False, "error_message": "HTTP 502 Bad Gateway"}
    assert classify_public_depth_improvement(L) == "degraded_or_noisy"


def test_repeated_depth_reduces_thin_fixture() -> None:
    """Empirical-style ledger: two-step iteration thin improves, joined rises."""
    step1 = build_public_depth_iteration_ledger(
        expansion_result={
            "ok": True,
            "before_metrics": {"thin_input_share": 0.5, "joined_recipe_substrate_row_count": 100},
            "after_metrics": {"thin_input_share": 0.45, "joined_recipe_substrate_row_count": 110},
            "before_exclusion_distribution": {"a": 1},
            "after_exclusion_distribution": {"a": 1},
            "expansion_summary_json": {"operations": []},
        },
        readiness_before={},
        readiness_after={},
        trig_before={},
        trig_after={},
    )
    assert step1["thin_input_share_delta"] == pytest.approx(-0.05)
    assert classify_public_depth_improvement(step1) == "meaningful_progress"


def test_marginal_only_fixture_conservative_signal() -> None:
    L = build_public_depth_iteration_ledger(
        expansion_result={
            "ok": True,
            "before_metrics": {"thin_input_share": 0.5, "joined_recipe_substrate_row_count": 100},
            "after_metrics": {"thin_input_share": 0.498, "joined_recipe_substrate_row_count": 102},
            "before_exclusion_distribution": {},
            "after_exclusion_distribution": {},
            "expansion_summary_json": {"operations": []},
        },
        readiness_before={},
        readiness_after={},
        trig_before={},
        trig_after={},
    )
    assert classify_public_depth_improvement(L) == "marginal_progress"
    sig, _rat = compute_public_depth_operator_signal(
        escalation_recommendation="hold_and_repeat_public_repair",
        depth_ledgers_newest_first=[L],
    )
    assert sig == "repeat_targeted_public_repair"


def test_infra_failed_depth_excluded_from_plateau_by_default() -> None:
    sid = str(uuid.uuid4())
    drid = str(uuid.uuid4())
    mock = MagicMock()
    mock.fetch_public_repair_iteration_series.return_value = {
        "id": sid,
        "program_id": str(uuid.uuid4()),
    }
    mock.list_public_repair_iteration_members_for_series.return_value = [
        {
            "member_kind": "public_depth",
            "public_depth_run_id": drid,
            "trend_snapshot_json": {"public_depth_run_id": drid},
        }
    ]
    mock.fetch_public_depth_run.return_value = {
        "id": drid,
        "status": "failed",
        "error_message": "HTTP 502 Bad Gateway",
    }
    with patch(
        "public_repair_iteration.service.dbrec.fetch_public_repair_iteration_series",
        mock.fetch_public_repair_iteration_series,
    ), patch(
        "public_repair_iteration.service.dbrec.list_public_repair_iteration_members_for_series",
        mock.list_public_repair_iteration_members_for_series,
    ), patch(
        "public_repair_iteration.service.dbrec.fetch_public_depth_run",
        mock.fetch_public_depth_run,
    ):
        out = collect_plateau_snapshots_for_series(
            mock, series_id=sid, exclude_infra_default=True
        )
    assert out["ok"] is True
    assert out["included_run_count"] == 0
    assert out["excluded_infra_failure_count"] == 1


def test_append_public_depth_idempotent() -> None:
    sid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    drid = str(uuid.uuid4())
    ledger = {
        "expansion_ok": True,
        "public_depth_run_id": drid,
        "joined_recipe_substrate_row_count_delta": 1,
        "thin_input_share_delta": 0,
        "improvement_classification": "marginal_progress",
        "rerun_gate_after": {"phase15": False, "phase16": False},
    }
    mock = MagicMock()
    mock.fetch_public_repair_iteration_series.return_value = {
        "id": sid,
        "status": "active",
        "policy_version": "1",
        "universe_name": "U",
    }
    mock.fetch_public_repair_iteration_member_by_depth_run_id.return_value = {
        "id": "existing-member",
    }
    with patch(
        "public_repair_iteration.depth_iteration.dbrec.fetch_public_repair_iteration_series",
        mock.fetch_public_repair_iteration_series,
    ), patch(
        "public_repair_iteration.depth_iteration.dbrec.fetch_public_repair_iteration_member_by_depth_run_id",
        mock.fetch_public_repair_iteration_member_by_depth_run_id,
    ), patch(
        "public_repair_iteration.depth_iteration.recompute_escalation_from_series_members",
        return_value={"escalation_recommendation": "hold_and_repeat_public_repair"},
    ):
        out = append_public_depth_expansion_to_iteration_series(
            mock,
            series_id=sid,
            program_id=pid,
            ledger=ledger,
            depth_run_row={"id": drid, "universe_name": "U", "status": "completed"},
        )
    assert out["ok"] is True
    assert out.get("idempotent") is True
    mock.insert_public_repair_iteration_member.assert_not_called()


@patch(
    "public_repair_iteration.depth_iteration.dbrec.list_public_repair_escalation_decisions_for_series"
)
@patch("public_repair_iteration.depth_iteration.compute_public_repair_plateau")
@patch("public_repair_iteration.depth_iteration.collect_plateau_snapshots_for_series")
@patch("public_repair_iteration.depth_iteration.dbrec.list_public_repair_iteration_members_for_series")
@patch("public_repair_iteration.depth_iteration.dbrec.fetch_public_repair_iteration_series")
def test_export_depth_series_brief_shape(
    mock_series: MagicMock,
    mock_members: MagicMock,
    mock_collect: MagicMock,
    mock_plateau: MagicMock,
    mock_esc: MagicMock,
) -> None:
    mock_series.return_value = {
        "id": "s1",
        "program_id": "p1",
        "universe_name": "U",
    }
    mock_members.return_value = [
        {
            "member_kind": "public_depth",
            "trend_snapshot_json": {
                "member_kind": "public_depth",
                "phase22_ledger": {
                    "improvement_classification": "marginal_progress",
                    "joined_recipe_substrate_row_count_delta": 2,
                    "dominant_exclusion_keys_after": ["x"],
                },
            },
        }
    ]
    mock_collect.return_value = {
        "ok": True,
        "included_run_count": 1,
        "excluded_runs": [],
    }
    mock_plateau.return_value = {
        "ok": True,
        "escalation_recommendation": "hold_and_repeat_public_repair",
        "plateau_metrics": {"n_iterations": 1},
    }
    mock_esc.return_value = [{"recommendation": "hold_and_repeat_public_repair"}]
    out = export_public_depth_series_brief(MagicMock(), series_id="s1")
    assert out["ok"] is True
    assert out["brief"]["version"] == 1
    assert out["brief"]["improvement_classifications_in_order"] == ["marginal_progress"]
    assert out["brief"]["public_depth_operator_signal"]


def test_phase22_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    for name in (
        "smoke-phase22-public-depth-iteration",
        "advance-public-depth-iteration",
        "export-public-depth-series-brief",
    ):
        assert name in sub.choices
