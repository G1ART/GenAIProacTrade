from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock, patch

import state_change.runner as sc_runner
from main import build_parser
from public_repair_iteration.escalation_policy import decide_escalation_recommendation
from public_repair_iteration.infra_noise import classify_infra_failure
from public_repair_iteration.resolver import (
    resolve_repair_campaign_latest_pair,
    resolve_repair_campaign_run_id,
)
from public_repair_iteration.service import collect_plateau_snapshots_for_series
from research_registry import promotion_rules


def test_runner_still_no_public_repair_iteration_reference() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_iteration" not in src
    assert "public_repair_campaign" not in src


def test_promotion_boundary_still_closed() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


def test_classify_infra_502_and_timeout() -> None:
    assert classify_infra_failure("HTTP 502 Bad Gateway") == "gateway_502"
    assert classify_infra_failure("read timed out") == "http_timeout"
    assert classify_infra_failure("ECONNRESET") == "connection_reset"
    assert classify_infra_failure("recipe validation failed") is None


def test_plateau_proof_continue_public_depth_strong_joined() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 40,
            "thin_input_share": 0.5,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
        {
            "joined_recipe_substrate_row_count": 70,
            "thin_input_share": 0.49,
            "final_decision": "continue_public_depth",
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "continue_public_depth"
    assert rat.get("rule") == "strong_joined_substrate_gain"


def test_plateau_proof_hold_mixed_signals() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 100,
            "thin_input_share": 0.33,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
        {
            "joined_recipe_substrate_row_count": 101,
            "thin_input_share": 0.34,
            "final_decision": "repair_insufficient_repeat_buildout",
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "hold_and_repeat_public_repair"
    assert rat.get("rule") == "mixed_or_inconclusive"


def test_plateau_proof_open_targeted_premium_discovery() -> None:
    snaps = [
        {
            "joined_recipe_substrate_row_count": 100,
            "thin_input_share": 0.5,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.1,
        },
        {
            "joined_recipe_substrate_row_count": 101,
            "thin_input_share": 0.51,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.15,
        },
        {
            "joined_recipe_substrate_row_count": 102,
            "thin_input_share": 0.52,
            "final_decision": "repair_insufficient_repeat_buildout",
            "premium_share_from_interp": 0.42,
        },
    ]
    rec, rat, _, _ = decide_escalation_recommendation(snaps)
    assert rec == "open_targeted_premium_discovery"
    assert "plateau" in rat.get("rule", "") or "premium" in rat.get("rule", "")


def test_collect_plateau_excludes_infra_failed_run_by_default() -> None:
    sid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    rid_ok = str(uuid.uuid4())
    rid_bad = str(uuid.uuid4())
    client = MagicMock()

    def _fetch_run(_client: MagicMock, *, run_id: str) -> dict | None:
        if run_id == rid_ok:
            return {
                "id": rid_ok,
                "program_id": pid,
                "universe_name": "U",
                "status": "completed",
                "final_decision": "repair_insufficient_repeat_buildout",
                "error_message": None,
            }
        if run_id == rid_bad:
            return {
                "id": rid_bad,
                "status": "failed",
                "error_message": "upstream returned 502",
                "final_decision": None,
            }
        return None

    with (
        patch(
            "public_repair_iteration.service.dbrec.fetch_public_repair_iteration_series",
            return_value={
                "id": sid,
                "program_id": pid,
                "universe_name": "U",
                "policy_version": "1",
                "status": "active",
            },
        ),
        patch(
            "public_repair_iteration.service.dbrec.list_public_repair_iteration_members_for_series",
            return_value=[
                {
                    "repair_campaign_run_id": rid_ok,
                    "trend_snapshot_json": {
                        "repair_campaign_run_id": rid_ok,
                        "joined_recipe_substrate_row_count": 10,
                        "thin_input_share": 0.5,
                        "final_decision": "repair_insufficient_repeat_buildout",
                    },
                },
                {
                    "repair_campaign_run_id": rid_bad,
                    "trend_snapshot_json": {
                        "repair_campaign_run_id": rid_bad,
                        "joined_recipe_substrate_row_count": 99,
                    },
                },
            ],
        ),
        patch(
            "public_repair_iteration.service.dbrec.fetch_public_repair_campaign_run",
            side_effect=_fetch_run,
        ),
    ):
        out = collect_plateau_snapshots_for_series(
            client, series_id=sid, exclude_infra_default=True
        )
    assert out["ok"] is True
    assert out["included_run_count"] == 1
    assert out["excluded_infra_failure_count"] == 1
    assert len(out["excluded_runs"]) == 1


def test_resolve_latest_compatible_requires_series() -> None:
    pid = str(uuid.uuid4())
    with patch(
        "public_repair_iteration.resolver.dbrec.fetch_research_program",
        return_value={"id": pid, "status": "active", "universe_name": "U"},
    ):
        out = resolve_repair_campaign_run_id(
            MagicMock(),
            "latest-compatible",
            program_id=pid,
        )
    assert out["ok"] is False
    assert "series_context_required" in str(out.get("error", ""))


def test_resolve_repair_campaign_latest_pair_insufficient() -> None:
    pid = str(uuid.uuid4())
    with (
        patch(
            "public_repair_iteration.resolver.dbrec.list_public_repair_campaign_runs_for_program",
            return_value=[],
        ),
        patch(
            "public_repair_iteration.resolver.dbrec.fetch_research_program",
            return_value={"id": pid, "status": "active", "universe_name": "U"},
        ),
    ):
        out = resolve_repair_campaign_latest_pair(
            MagicMock(),
            program_id=pid,
            series={"universe_name": "U", "policy_version": "1", "id": "s"},
            compatible=True,
        )
    assert out["ok"] is False


def test_phase21_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    assert "advance-public-repair-series" in sub.choices
    assert "resolve-repair-campaign-pair" in sub.choices
