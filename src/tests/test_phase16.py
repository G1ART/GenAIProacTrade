from __future__ import annotations

import inspect
import pytest

import state_change.runner as sc_runner
from research_registry import promotion_rules
from research_validation.constants import (
    CANONICAL_COHORT_DIMENSIONS,
    COHORT_CONFIG_VERSION,
    JOIN_POLICY_VERSION,
    WINDOW_STABILITY_METRIC_KEY,
)
from validation_campaign.constants import canonical_baseline_config
from validation_campaign.compatibility import is_recipe_validation_run_compatible
from validation_campaign.constants import STRATEGIC_RECOMMENDATIONS
from validation_campaign.decision_gate import assert_bounded_recommendation, decide_strategic_recommendation
from validation_campaign.service import hypothesis_campaign_eligible


def test_runner_does_not_reference_validation_campaign() -> None:
    src = inspect.getsource(sc_runner)
    assert "validation_campaign" not in src


def test_promotion_rules_guard_includes_validation_campaign() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


def test_hypothesis_eligibility() -> None:
    prog = {"status": "active", "id": "p1"}
    h_ok = {"id": "h1", "status": "sandboxed"}
    h_bad = {"id": "h2", "status": "proposed"}
    rev = [{"id": "r1"}]
    ref = [{"id": "f1"}]
    assert hypothesis_campaign_eligible(h_ok, prog, rev, ref)[0] is True
    assert hypothesis_campaign_eligible(h_bad, prog, rev, ref)[0] is False
    assert hypothesis_campaign_eligible(h_ok, {**prog, "status": "archived"}, rev, ref)[0] is False
    assert hypothesis_campaign_eligible(h_ok, prog, [], ref)[0] is False
    assert hypothesis_campaign_eligible(h_ok, prog, rev, [])[0] is False


def test_compatibility_requires_canonical_configs() -> None:
    base = canonical_baseline_config()
    run_ok = {
        "status": "completed",
        "join_policy_version": JOIN_POLICY_VERSION,
        "baseline_config_json": base,
        "cohort_config_json": {
            "config_version": COHORT_CONFIG_VERSION,
            "dimensions": list(CANONICAL_COHORT_DIMENSIONS),
            "program_quality_class": "thin_input",
        },
        "window_config_json": {"stability_metric": WINDOW_STABILITY_METRIC_KEY},
        "quality_filter_json": {"join_policy_version": JOIN_POLICY_VERSION},
    }
    assert is_recipe_validation_run_compatible(run_ok, program_quality_class="thin_input") is True
    assert is_recipe_validation_run_compatible(run_ok, program_quality_class="strong") is False

    run_bad = {**run_ok, "join_policy_version": "legacy"}
    assert is_recipe_validation_run_compatible(run_bad, program_quality_class="thin_input") is False


def test_recommendation_enum_bounded() -> None:
    for r in STRATEGIC_RECOMMENDATIONS:
        assert assert_bounded_recommendation(r) == r
    with pytest.raises(ValueError):
        assert_bounded_recommendation("vibes_first")


def test_decision_routes_public_depth_thin_campaign() -> None:
    rec, detail = decide_strategic_recommendation(
        {
            "n_eligible": 3,
            "n_validated": 3,
            "n_members_strong_or_usable_context": 0,
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 0,
            "n_failure_cases_with_nonempty_premium_hint": 1,
            "thin_input_failure_share": 0.5,
            "degraded_or_failed_context_failure_share": 0.0,
            "dominant_program_quality_class": "thin_input",
        }
    )
    assert rec == "public_data_depth_first"
    assert "thin" in detail.get("rule", "") or "program_qc" in detail.get("rule", "")


def test_decision_routes_premium_seam() -> None:
    rec, _ = decide_strategic_recommendation(
        {
            "n_eligible": 4,
            "n_validated": 4,
            "n_members_strong_or_usable_context": 3,
            "total_failure_cases_across_members": 10,
            "n_contradictory_failure_cases": 5,
            "n_failure_cases_with_nonempty_premium_hint": 2,
            "thin_input_failure_share": 0.05,
            "degraded_or_failed_context_failure_share": 0.05,
            "dominant_program_quality_class": "strong",
        }
    )
    assert rec == "targeted_premium_seam_first"


def test_decision_routes_insufficient_evidence() -> None:
    rec, _ = decide_strategic_recommendation(
        {
            "n_eligible": 1,
            "n_validated": 0,
            "dominant_program_quality_class": "thin_input",
        }
    )
    assert rec == "insufficient_evidence_repeat_campaign"


def test_exported_brief_shape() -> None:
    from validation_campaign.service import render_decision_brief_markdown

    brief = {
        "campaign_run_id": "c1",
        "program": {"title": "T", "research_question": "Q?"},
        "recommendation": "public_data_depth_first",
        "rationale_text": "because",
        "hypotheses_included": [
            {"hypothesis_id": "h1", "validation_run_id": "v1", "survival_status": "weak_survival"}
        ],
        "survival_distribution": {
            "survives": 0,
            "weak_survival": 1,
            "demote_to_sandbox": 0,
            "archive_failed": 0,
        },
        "top_failure_rationales": [("fragile", 1)],
        "top_premium_hint_tokens": [],
        "counterfactual_next_step": {"if_more_data": "re-run"},
    }
    md = render_decision_brief_markdown(brief)
    assert "public_data_depth_first" in md
    assert "weak_survival" in md


def test_compatibility_allows_legacy_cohort_config_version_null() -> None:
    run = {
        "status": "completed",
        "join_policy_version": JOIN_POLICY_VERSION,
        "baseline_config_json": canonical_baseline_config(),
        "cohort_config_json": {
            "dimensions": list(CANONICAL_COHORT_DIMENSIONS),
            "program_quality_class": "usable_with_gaps",
        },
        "window_config_json": {"stability_metric": WINDOW_STABILITY_METRIC_KEY},
        "quality_filter_json": {},
    }
    assert is_recipe_validation_run_compatible(run, program_quality_class="usable_with_gaps") is True
