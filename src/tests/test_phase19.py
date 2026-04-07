from __future__ import annotations

import inspect

import state_change.runner as sc_runner
from main import build_parser
from public_repair_campaign.comparisons import (
    build_improvement_interpretation,
    compare_survival_distributions,
)
from public_repair_campaign.constants import FINAL_DECISIONS, REPAIR_CAMPAIGN_POLICY_VERSION
from public_repair_campaign.decision_policy import (
    assert_final_decision,
    decide_final_repair_branch,
    premium_evidence_from_campaign_metrics,
    substrate_improved_from_buildout,
)
from research_registry import promotion_rules


def test_runner_does_not_reference_public_repair_campaign() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_campaign" not in src


def test_promotion_rules_guard_includes_public_repair_campaign() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()
    boundary = promotion_rules.describe_production_boundary()
    prod = str(boundary.get("production_scoring_rule") or "")
    assert "Phase 19" in prod or "public_repair_campaign" in prod


def test_compare_survival_distributions_deltas() -> None:
    before = {"survives": 1, "weak_survival": 2, "archive_failed": 1}
    after = {"survives": 3, "weak_survival": 1, "archive_failed": 0}
    cmp = compare_survival_distributions(before, after)
    assert cmp["deltas"]["survives"] == 2
    assert cmp["deltas"]["weak_survival"] == -1
    assert cmp["deltas"]["archive_failed"] == -1
    assert cmp["outcome_improved_heuristic"] is True


def test_build_improvement_interpretation_premium_share() -> None:
    interp = build_improvement_interpretation(
        survival_compare={"deltas": {}},
        before_rec="public_data_depth_first",
        after_rec="public_data_depth_first",
        after_campaign_metrics={
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 4,
            "n_failure_cases_with_nonempty_premium_hint": 0,
        },
    )
    assert interp["recommendation_changed"] is False
    assert interp["after_campaign_failure_totals"]["premium_share"] == 0.4


def test_substrate_improved_from_buildout() -> None:
    imp = {
        "substrate_uplift": {"joined_substrate_improved": True},
        "exclusion_improvement": {"tracked": {}},
    }
    assert substrate_improved_from_buildout(imp) is True
    assert substrate_improved_from_buildout(None) is False


def test_premium_seam_requires_post_repair_rerun() -> None:
    dec, rat = decide_final_repair_branch(
        substrate_improved=True,
        reruns_executed=False,
        improvement_summary={},
        survival_compare={"outcome_improved_heuristic": True, "deltas": {}},
        before_campaign_recommendation="public_data_depth_first",
        after_campaign_recommendation="targeted_premium_seam_first",
        after_campaign_metrics=None,
    )
    assert dec == "repair_insufficient_repeat_buildout"
    assert rat.get("rule") == "no_post_repair_rerun_evidence"


def test_premium_branch_when_rerun_and_phase16_rec() -> None:
    dec, _ = decide_final_repair_branch(
        substrate_improved=True,
        reruns_executed=True,
        improvement_summary={"substrate_uplift": {"joined_substrate_improved": True}},
        survival_compare={"outcome_improved_heuristic": False, "deltas": {}},
        before_campaign_recommendation="public_data_depth_first",
        after_campaign_recommendation="targeted_premium_seam_first",
        after_campaign_metrics=None,
    )
    assert dec == "consider_targeted_premium_seam"


def test_premium_branch_metrics_share_gate() -> None:
    dec, rat = decide_final_repair_branch(
        substrate_improved=True,
        reruns_executed=True,
        improvement_summary={"substrate_uplift": {"joined_substrate_improved": True}},
        survival_compare={"outcome_improved_heuristic": False, "deltas": {}},
        before_campaign_recommendation="public_data_depth_first",
        after_campaign_recommendation="public_data_depth_first",
        after_campaign_metrics={
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 4,
            "n_failure_cases_with_nonempty_premium_hint": 0,
        },
    )
    assert dec == "consider_targeted_premium_seam"
    assert rat.get("rule") == "premium_signal_share_after_rerun"


def test_continue_public_depth_on_survival_improvement() -> None:
    dec, rat = decide_final_repair_branch(
        substrate_improved=True,
        reruns_executed=True,
        improvement_summary={},
        survival_compare={"outcome_improved_heuristic": True, "deltas": {"survives": 1}},
        before_campaign_recommendation="public_data_depth_first",
        after_campaign_recommendation="public_data_depth_first",
        after_campaign_metrics={"total_failure_cases_across_members": 0},
    )
    assert dec == "continue_public_depth"
    assert rat.get("rule") == "survival_outcomes_improved"


def test_final_decision_enum_bounded() -> None:
    for d in FINAL_DECISIONS:
        assert assert_final_decision(d) == d


def test_premium_evidence_helper() -> None:
    assert premium_evidence_from_campaign_metrics(
        {
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 4,
            "n_failure_cases_with_nonempty_premium_hint": 0,
        }
    )
    assert not premium_evidence_from_campaign_metrics(
        {
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 0,
            "n_failure_cases_with_nonempty_premium_hint": 5,
        }
    )


def test_phase19_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    for cmd in (
        "smoke-phase19-public-repair-campaign",
        "run-public-repair-campaign",
        "report-public-repair-campaign",
        "compare-repair-revalidation-outcomes",
        "export-public-repair-decision-brief",
        "list-repair-campaigns",
    ):
        assert cmd in names


def test_policy_version_constant() -> None:
    assert REPAIR_CAMPAIGN_POLICY_VERSION == "1"


def test_repair_insufficient_when_substrate_not_improved_after_rerun() -> None:
    dec, _ = decide_final_repair_branch(
        substrate_improved=False,
        reruns_executed=True,
        improvement_summary={},
        survival_compare={"outcome_improved_heuristic": True, "deltas": {}},
        before_campaign_recommendation="public_data_depth_first",
        after_campaign_recommendation="public_data_depth_first",
        after_campaign_metrics=None,
    )
    assert dec == "repair_insufficient_repeat_buildout"
