"""Phase 24: branch census, plateau review, alternating cycle (unit tests)."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

import state_change.runner as sc_runner
from operator_closeout.next_step import choose_post_patch_next_action_from_signals
from public_first.census import aggregate_census_from_series_rows
from public_first.cycle import (
    recommend_next_public_first_command,
    write_latest_public_first_review_md,
)
from public_first.plateau_review import (
    MIXED_OR_INSUFFICIENT_EVIDENCE,
    PREMIUM_DISCOVERY_REVIEW_PREPARABLE,
    PUBLIC_FIRST_STILL_IMPROVING,
    conclude_public_first_plateau_review,
)


def test_runner_still_no_public_repair_iteration_reference() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_iteration" not in src
    assert "public_repair_campaign" not in src


def _series_row(sid: str, status: str = "active") -> dict:
    return {"id": sid, "status": status, "universe_name": "u1", "policy_version": "1"}


def _coll(ok: bool, inc: int, infra: int, other: int = 0) -> dict:
    return {
        "ok": ok,
        "included_run_count": inc,
        "excluded_infra_failure_count": infra,
        "excluded_other_count": other,
    }


def test_aggregate_census_mixed_repair_depth_classifications() -> None:
    brief1 = {
        "brief": {
            "persisted_escalation_branch_counts": {"hold_and_repeat_public_repair": 2},
            "public_depth_operator_signal": "repeat_targeted_public_repair",
            "improvement_classification_counts": {"meaningful_progress": 1},
            "improvement_classifications_in_order": ["meaningful_progress", "marginal_progress"],
            "public_depth_run_ids_for_classifications": ["d1", "d2"],
            "dominant_exclusions_latest_after": ["thin_input"],
            "escalation_recommendation_current": "hold_and_repeat_public_repair",
        }
    }
    brief2 = {
        "brief": {
            "persisted_escalation_branch_counts": {"continue_public_depth": 1},
            "public_depth_operator_signal": "continue_public_depth_buildout",
            "improvement_classification_counts": {"marginal_progress": 1},
            "improvement_classifications_in_order": ["marginal_progress"],
            "public_depth_run_ids_for_classifications": ["d3"],
            "dominant_exclusions_latest_after": ["x"],
        }
    }
    triples = [
        (_series_row("s1"), brief1, _coll(True, 3, 1)),
        (_series_row("s2"), brief2, _coll(True, 2, 0)),
    ]
    out = aggregate_census_from_series_rows(
        triples,
        program_id="p1",
        universe_name="u1",
        active_series_id="s1",
        exclusions=[],
    )
    assert out["series_included_count"] == 2
    assert out["aggregated_persisted_escalation_branch_counts"]["hold_and_repeat_public_repair"] == 2
    assert out["aggregated_persisted_escalation_branch_counts"]["continue_public_depth"] == 1
    assert out["sum_included_run_count"] == 5
    assert out["sum_excluded_infra_failure_count"] == 1
    assert out["deduped_improvement_classification_counts"]["meaningful_progress"] == 1
    assert out["deduped_improvement_classification_counts"]["marginal_progress"] == 2


def test_aggregate_dedupes_same_depth_run_across_series() -> None:
    brief_a = {
        "brief": {
            "persisted_escalation_branch_counts": {},
            "public_depth_operator_signal": "x",
            "improvement_classification_counts": {},
            "improvement_classifications_in_order": ["meaningful_progress"],
            "public_depth_run_ids_for_classifications": ["same-id"],
        }
    }
    brief_b = {
        "brief": {
            "persisted_escalation_branch_counts": {},
            "public_depth_operator_signal": "x",
            "improvement_classification_counts": {},
            "improvement_classifications_in_order": ["meaningful_progress"],
            "public_depth_run_ids_for_classifications": ["same-id"],
        }
    }
    triples = [
        (_series_row("a"), brief_a, _coll(True, 1, 0)),
        (_series_row("b"), brief_b, _coll(True, 1, 0)),
    ]
    out = aggregate_census_from_series_rows(
        triples,
        program_id="p",
        universe_name="u",
        active_series_id="a",
        exclusions=[{"reason": "deduplication_skipped_duplicate_artifacts", "n_total": 1}],
    )
    assert out["deduped_improvement_classification_counts"].get("meaningful_progress", 0) == 1


def test_plateau_review_premium_preparable() -> None:
    census = {
        "active_series_snapshot": {
            "escalation_recommendation_current": "open_targeted_premium_discovery"
        },
        "deduped_improvement_classification_counts": {},
    }
    out = conclude_public_first_plateau_review(census=census)
    assert out["conclusion"] == PREMIUM_DISCOVERY_REVIEW_PREPARABLE
    assert out["premium_live_integration"] is False


def test_plateau_review_still_improving() -> None:
    census = {
        "active_series_snapshot": {"escalation_recommendation_current": "continue_public_depth"},
        "deduped_improvement_classification_counts": {
            "meaningful_progress": 2,
            "marginal_progress": 1,
            "no_material_progress": 1,
        },
    }
    out = conclude_public_first_plateau_review(census=census)
    assert out["conclusion"] == PUBLIC_FIRST_STILL_IMPROVING


def test_plateau_review_mixed_insufficient() -> None:
    census = {
        "active_series_snapshot": {"escalation_recommendation_current": "hold_and_repeat_public_repair"},
        "deduped_improvement_classification_counts": {"no_material_progress": 1},
    }
    out = conclude_public_first_plateau_review(census=census)
    assert out["conclusion"] == MIXED_OR_INSUFFICIENT_EVIDENCE


def test_coordinator_depth_path_via_phase23_chooser() -> None:
    out = choose_post_patch_next_action_from_signals(
        escalation_recommendation="continue_public_depth",
        depth_operator_signal="continue_public_depth_buildout",
        verify_only=False,
    )
    assert out["action"] == "advance_public_depth_iteration"


def test_coordinator_repair_path_via_phase23_chooser() -> None:
    out = choose_post_patch_next_action_from_signals(
        escalation_recommendation="hold_and_repeat_public_repair",
        depth_operator_signal="repeat_targeted_public_repair",
        verify_only=False,
    )
    assert out["action"] == "advance_repair_series"


def test_recommend_next_command_premium_branch() -> None:
    s = recommend_next_public_first_command(
        universe="sp500_current",
        plateau_conclusion=PREMIUM_DISCOVERY_REVIEW_PREPARABLE,
        executed_action=None,
    )
    assert "프리미엄" in s or "premium" in s.lower() or "escalation" in s


def test_write_latest_public_first_review_md(tmp_path) -> None:
    p = tmp_path / "latest_public_first_review.md"
    write_latest_public_first_review_md(
        p,
        census={
            "series_included_count": 1,
            "sum_included_run_count": 2,
            "sum_excluded_infra_failure_count": 0,
            "aggregated_persisted_escalation_branch_counts": {"hold_and_repeat_public_repair": 3},
            "aggregated_depth_operator_signal_counts": {"repeat_targeted_public_repair": 1},
            "deduped_improvement_classification_counts": {},
            "latest_rerun_readiness": {"ok": True},
            "exclusions": [],
        },
        plateau_review={
            "conclusion": MIXED_OR_INSUFFICIENT_EVIDENCE,
            "reason": "test",
            "premium_live_integration": False,
        },
        cycle_payload=None,
        recommended_command="run-post-patch-closeout --universe u",
    )
    text = p.read_text(encoding="utf-8")
    assert "Phase 24" in text
    assert "Recommended next command" in text


def test_advance_public_first_cycle_premium_hold_no_advance(tmp_path) -> None:
    from config import Settings
    from public_first.cycle import advance_public_first_cycle

    settings = MagicMock(spec=Settings)
    census = {
        "ok": True,
        "series_included_count": 1,
        "active_series_snapshot": {
            "escalation_recommendation_current": "open_targeted_premium_discovery"
        },
        "deduped_improvement_classification_counts": {},
        "aggregated_persisted_escalation_branch_counts": {},
        "aggregated_depth_operator_signal_counts": {},
        "sum_included_run_count": 0,
        "sum_excluded_infra_failure_count": 0,
        "sum_excluded_other_count": 0,
        "latest_dominant_exclusion_keys_merged": [],
        "exclusions": [],
        "latest_rerun_readiness": {"ok": True},
        "series_ids_included": ["s1"],
    }

    with (
        patch("public_first.cycle.get_supabase_client") as m_client,
        patch("public_first.cycle.build_public_first_branch_census", return_value=census),
        patch(
            "public_first.cycle.resolve_iteration_series_for_operator",
            return_value={"ok": True, "series_id": "s1"},
        ),
        patch("public_first.cycle.advance_public_repair_series") as m_adv_r,
        patch("public_first.cycle.advance_public_depth_iteration") as m_adv_d,
    ):
        m_client.return_value = MagicMock()
        out = advance_public_first_cycle(
            settings,
            program_id="p1",
            universe_name="u1",
            out_stem=str(tmp_path),
        )
    assert out["chosen_action"] == "hold_for_plateau_review"
    assert out["executed"] is False
    m_adv_r.assert_not_called()
    m_adv_d.assert_not_called()
    assert (tmp_path / "latest_public_first_review.md").is_file()


def test_advance_public_first_cycle_alternating_depth_then_repair(tmp_path) -> None:
    from config import Settings
    from public_first.cycle import advance_public_first_cycle

    settings = MagicMock(spec=Settings)
    census = {
        "ok": True,
        "series_included_count": 1,
        "active_series_snapshot": {"escalation_recommendation_current": "continue_public_depth"},
        "deduped_improvement_classification_counts": {
            "meaningful_progress": 2,
            "marginal_progress": 1,
        },
        "aggregated_persisted_escalation_branch_counts": {},
        "aggregated_depth_operator_signal_counts": {},
        "sum_included_run_count": 2,
        "sum_excluded_infra_failure_count": 0,
        "sum_excluded_other_count": 0,
        "latest_dominant_exclusion_keys_merged": [],
        "exclusions": [],
        "latest_rerun_readiness": {"ok": True},
        "series_ids_included": ["s1"],
    }
    last_member = {"member_kind": "public_depth", "public_depth_run_id": "d1"}

    with (
        patch("public_first.cycle.get_supabase_client") as m_client,
        patch("public_first.cycle.build_public_first_branch_census", return_value=census),
        patch(
            "public_first.cycle.resolve_iteration_series_for_operator",
            return_value={"ok": True, "series_id": "s1"},
        ),
        patch(
            "public_first.cycle.dbrec.list_public_repair_iteration_members_for_series",
            return_value=[last_member],
        ),
        patch(
            "public_first.cycle.advance_public_repair_series",
            return_value={"ok": True, "operator_summary": "ok"},
        ) as m_adv_r,
        patch("public_first.cycle.advance_public_depth_iteration") as m_adv_d,
    ):
        m_client.return_value = MagicMock()
        out = advance_public_first_cycle(
            settings,
            program_id="p1",
            universe_name="u1",
            out_stem=str(tmp_path),
        )
    assert out["chosen_action"] == "advance_repair_series"
    assert out["executed"] is True
    m_adv_r.assert_called_once()
    m_adv_d.assert_not_called()


def test_main_registers_phase24_commands() -> None:
    from main import build_parser

    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "choices", None))
    names = set(sub.choices.keys())
    assert "report-public-first-branch-census" in names
    assert "export-public-first-branch-census-brief" in names
    assert "export-public-first-plateau-review-brief" in names
    assert "run-public-first-plateau-review" in names
    assert "advance-public-first-cycle" in names
