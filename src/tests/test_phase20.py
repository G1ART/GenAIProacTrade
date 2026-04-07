from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock, patch

import state_change.runner as sc_runner
from main import build_parser
from public_repair_iteration.escalation_policy import decide_escalation_recommendation
from public_repair_iteration.resolver import resolve_program_id, resolve_repair_campaign_run_id
from research_registry import promotion_rules


def test_runner_does_not_reference_public_repair_iteration() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_iteration" not in src


def test_promotion_boundary_mentions_phase20_iteration() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()
    b = promotion_rules.describe_production_boundary()
    prod = str(b.get("production_scoring_rule") or "")
    assert "Phase 20" in prod or "public_repair_iteration" in prod


def test_escalation_hold_when_insufficient_iterations() -> None:
    rec, rat, _p, _c = decide_escalation_recommendation(
        [{"joined_recipe_substrate_row_count": 100}]
    )
    assert rec == "hold_and_repeat_public_repair"
    assert rat.get("rule") == "insufficient_iterations"


def test_escalation_continue_on_strong_joined_delta() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 50,
            "thin_input_share": 0.5,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
        {
            "joined_recipe_substrate_row_count": 90,
            "thin_input_share": 0.48,
            "final_decision": "continue_public_depth",
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "continue_public_depth"
    assert rat.get("rule") == "strong_joined_substrate_gain"


def test_escalation_hold_mixed_default() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 100,
            "thin_input_share": 0.3,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
        {
            "joined_recipe_substrate_row_count": 102,
            "thin_input_share": 0.31,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "hold_and_repeat_public_repair"
    assert rat.get("rule") == "mixed_or_inconclusive"


def test_escalation_open_premium_plateau_with_signal() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 100,
            "thin_input_share": 0.5,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.1,
        },
        {
            "joined_recipe_substrate_row_count": 102,
            "thin_input_share": 0.52,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.2,
        },
        {
            "joined_recipe_substrate_row_count": 103,
            "thin_input_share": 0.55,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.4,
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "open_targeted_premium_discovery"
    assert "plateau" in rat.get("rule", "") or "premium" in rat.get("rule", "")


@patch("public_repair_iteration.resolver.dbrec.fetch_research_program")
def test_resolve_program_explicit_uuid(mock_fetch: MagicMock) -> None:
    pid = str(uuid.uuid4())
    mock_fetch.return_value = {"id": pid, "universe_name": "U"}
    out = resolve_program_id(MagicMock(), pid)
    assert out["ok"] is True
    assert out["program_id"] == pid


def test_resolve_program_invalid_uuid() -> None:
    out = resolve_program_id(MagicMock(), "not-a-uuid")
    assert out["ok"] is False


@patch("public_repair_iteration.resolver.dbrec.fetch_public_repair_campaign_run")
def test_resolve_repair_explicit_uuid_program_mismatch(mock_fetch: MagicMock) -> None:
    rid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    mock_fetch.return_value = {
        "id": rid,
        "program_id": str(uuid.uuid4()),
        "status": "completed",
        "final_decision": "continue_public_depth",
    }
    out = resolve_repair_campaign_run_id(MagicMock(), rid, program_id=pid)
    assert out["ok"] is False
    assert out["error"] == "repair_campaign_program_mismatch"


def test_phase20_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    for cmd in (
        "smoke-phase20-repair-iteration",
        "smoke-phase21-iteration-governance",
        "run-public-repair-iteration",
        "report-public-repair-iteration-history",
        "report-public-repair-plateau",
        "export-public-repair-escalation-brief",
        "list-public-repair-series",
        "report-latest-repair-state",
        "report-premium-discovery-readiness",
        "pause-public-repair-series",
        "resume-public-repair-series",
        "close-public-repair-series",
        "advance-public-repair-series",
        "resolve-repair-campaign-pair",
        "smoke-phase22-public-depth-iteration",
        "advance-public-depth-iteration",
        "export-public-depth-series-brief",
    ):
        assert cmd in names


@patch("public_repair_iteration.service.collect_plateau_snapshots_for_series")
@patch("public_repair_iteration.service.compute_public_repair_plateau")
def test_export_brief_includes_recommendation_keys(
    mock_plateau: MagicMock, mock_collect: MagicMock
) -> None:
    from public_repair_iteration.service import export_public_repair_escalation_brief

    mock_plateau.return_value = {
        "ok": True,
        "escalation_recommendation": "hold_and_repeat_public_repair",
        "rationale": {"rule": "mixed"},
        "plateau_metrics": {"n_iterations": 2},
        "counterfactual": {"if_more_iterations": "x"},
        "excluded_runs": [],
    }
    mock_collect.return_value = {
        "ok": True,
        "snapshots": [],
        "excluded_runs": [],
        "included_run_count": 0,
        "excluded_infra_failure_count": 0,
        "excluded_other_count": 0,
        "n_iteration_members_total": 0,
    }
    mock = MagicMock()
    mock.fetch_public_repair_iteration_series.return_value = {
        "id": "s1",
        "program_id": "p1",
        "universe_name": "U",
        "policy_version": "1",
        "status": "active",
    }
    mock.list_public_repair_escalation_decisions_for_series.return_value = [
        {
            "recommendation": "hold_and_repeat_public_repair",
            "rationale": "hold: mixed",
            "plateau_metrics_json": {},
            "counterfactual_json": {},
        }
    ]

    with (
        patch(
            "public_repair_iteration.service.dbrec.fetch_public_repair_iteration_series",
            mock.fetch_public_repair_iteration_series,
        ),
        patch(
            "public_repair_iteration.service.dbrec.list_public_repair_escalation_decisions_for_series",
            mock.list_public_repair_escalation_decisions_for_series,
        ),
    ):
        out = export_public_repair_escalation_brief(mock, series_id="s1")
    assert out["ok"] is True
    assert out["brief"].get("version") == 2
    assert out["brief"]["recomputed_from_members"]["recommendation"] == (
        "hold_and_repeat_public_repair"
    )
    assert "markdown" in out
