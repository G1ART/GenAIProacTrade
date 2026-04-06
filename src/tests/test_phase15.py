"""Phase 15 recipe validation lab tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from research_registry import promotion_rules
from research_validation.constants import (
    BASELINE_NAIVE,
    BASELINE_SIZE,
    BASELINE_STATE_CHANGE,
    MIN_SAMPLE_ROWS,
    SURVIVAL_STATUSES,
)
from research_validation.metrics import (
    pick_state_change_at_or_before_signal,
    state_change_rows_by_cik_sorted,
    top_bottom_spread,
)
from research_validation.policy import decide_survival
from research_validation.scorecard import build_scorecard
from research_validation.service import _best_worst_cohort, run_recipe_validation


def test_only_reviewed_hypotheses_can_be_validated() -> None:
    client = MagicMock()
    client.table.return_value = MagicMock()
    with (
        patch(
            "research_validation.service.dbrec.fetch_research_hypothesis",
            return_value={
                "id": "h1",
                "program_id": "p1",
                "status": "candidate_recipe",
                "feature_definition_json": {"families": []},
            },
        ),
        patch("research_validation.service.dbrec.fetch_research_reviews_for_hypothesis", return_value=[]),
    ):
        out = run_recipe_validation(client, hypothesis_id="h1")
    assert out.get("ok") is False
    assert out.get("error") == "reviews_required"


def test_proposed_hypothesis_cannot_validate() -> None:
    client = MagicMock()
    with (
        patch(
            "research_validation.service.dbrec.fetch_research_hypothesis",
            return_value={
                "id": "h1",
                "program_id": "p1",
                "status": "proposed",
                "feature_definition_json": {},
            },
        ),
        patch(
            "research_validation.service.dbrec.fetch_research_reviews_for_hypothesis",
            return_value=[{"id": "r1"}],
        ),
    ):
        out = run_recipe_validation(client, hypothesis_id="h1")
    assert out.get("ok") is False
    assert "candidate_recipe_or_sandboxed" in str(out.get("error", ""))


def test_explicit_baselines_are_defined() -> None:
    names = {BASELINE_STATE_CHANGE, BASELINE_NAIVE, BASELINE_SIZE}
    assert len(names) == 3


def test_thin_input_heavy_cannot_clean_survives() -> None:
    out = decide_survival(
        hypothesis_status="candidate_recipe",
        program_quality_class="thin_input",
        recipe_spread_pooled=0.08,
        sc_spread_pooled=0.01,
        mcap_spread_pooled=0.01,
        beats_state_change=True,
        beats_naive=True,
        beats_size=True,
        window_stability_ratio=0.95,
        contradiction_residual_count=0,
        thin_input_heavy=True,
        failed_degraded_emphasis=False,
    )
    assert out["survival_status"] == "weak_survival"
    assert out["survival_status"] in SURVIVAL_STATUSES


def test_sandbox_cannot_survives_even_when_strong() -> None:
    out = decide_survival(
        hypothesis_status="sandboxed",
        program_quality_class="strong",
        recipe_spread_pooled=0.08,
        sc_spread_pooled=0.01,
        mcap_spread_pooled=0.01,
        beats_state_change=True,
        beats_naive=True,
        beats_size=True,
        window_stability_ratio=0.95,
        contradiction_residual_count=0,
        thin_input_heavy=False,
        failed_degraded_emphasis=False,
    )
    assert out["survival_status"] != "survives"
    assert out["survival_status"] in SURVIVAL_STATUSES


def test_survival_status_always_bounded_enum() -> None:
    scenarios = [
        dict(
            hypothesis_status="candidate_recipe",
            program_quality_class="strong",
            recipe_spread_pooled=None,
            sc_spread_pooled=0.01,
            mcap_spread_pooled=None,
            beats_state_change=False,
            beats_naive=False,
            beats_size=False,
            window_stability_ratio=0.5,
            contradiction_residual_count=0,
            thin_input_heavy=False,
            failed_degraded_emphasis=False,
        ),
        dict(
            hypothesis_status="candidate_recipe",
            program_quality_class="strong",
            recipe_spread_pooled=0.0,
            sc_spread_pooled=0.02,
            mcap_spread_pooled=0.0,
            beats_state_change=False,
            beats_naive=False,
            beats_size=False,
            window_stability_ratio=0.9,
            contradiction_residual_count=3,
            thin_input_heavy=False,
            failed_degraded_emphasis=False,
        ),
    ]
    for kw in scenarios:
        out = decide_survival(**kw)
        assert out["survival_status"] in SURVIVAL_STATUSES


def test_failed_quality_caps_below_survives() -> None:
    out = decide_survival(
        hypothesis_status="candidate_recipe",
        program_quality_class="failed",
        recipe_spread_pooled=0.09,
        sc_spread_pooled=0.01,
        mcap_spread_pooled=0.01,
        beats_state_change=True,
        beats_naive=True,
        beats_size=True,
        window_stability_ratio=0.95,
        contradiction_residual_count=0,
        thin_input_heavy=False,
        failed_degraded_emphasis=True,
    )
    assert out["survival_status"] in ("demote_to_sandbox", "archive_failed", "weak_survival")
    assert out["survival_status"] not in ("survives",)


@pytest.mark.parametrize(
    "pairs,expected_sign",
    [
        ([(0.0, -0.02), (1.0, 0.05), (2.0, 0.06), (3.0, 0.07)] * 5, "positive"),
    ],
)
def test_top_bottom_spread_monotonic(pairs: list, expected_sign: str) -> None:
    sp = top_bottom_spread(pairs)
    assert sp is not None
    if expected_sign == "positive":
        assert sp > 0


def test_best_worst_cohort_from_results() -> None:
    rows = [
        {
            "baseline_name": "recipe",
            "metric_name": "top_bottom_spread_excess",
            "cohort_key": "pooled",
            "metric_value": 0.01,
        },
        {
            "baseline_name": "recipe",
            "metric_name": "top_bottom_spread_excess",
            "cohort_key": "year:2022",
            "metric_value": 0.08,
        },
        {
            "baseline_name": "recipe",
            "metric_name": "top_bottom_spread_excess",
            "cohort_key": "year:2023",
            "metric_value": -0.02,
        },
    ]
    best, worst = _best_worst_cohort(rows)
    assert "2022" in best
    assert "2023" in worst


def test_scorecard_includes_cohorts_and_fragility() -> None:
    card = build_scorecard(
        hypothesis={"hypothesis_title": "T", "economic_rationale": "E"},
        program={"research_question": "Q?"},
        validation_run={"id": "vr1"},
        comparisons=[{"baseline_name": "x"}],
        survival={
            "survival_status": "weak_survival",
            "rationale": "r",
            "fragility_json": {"k": 1},
        },
        failure_cases=[],
        summary={
            "strongest_positive": "p",
            "strongest_fragility": "f",
            "best_cohort": "year:2020",
            "worst_cohort": "year:2021",
            "residual_contradiction_count": 2,
        },
    )
    assert card["best_cohort"] == "year:2020"
    assert card["worst_cohort"] == "year:2021"
    assert card["fragility_json"] == {"k": 1}
    assert "residual_contradiction_count" in card


def test_state_change_runner_does_not_reference_validation_lab() -> None:
    p = Path(__file__).resolve().parents[1] / "state_change" / "runner.py"
    text = p.read_text(encoding="utf-8")
    assert "research_validation" not in text


def test_promotion_guard_passes() -> None:
    promotion_rules.assert_no_auto_promotion_wiring()


def test_run_inserts_failure_batch_when_cohort_weak(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list] = {}

    def _capture_failures(_client: object, rows: list) -> None:
        captured["failures"] = list(rows)

    panels = []
    for i in range(30):
        panels.append(
            {
                "cik": f"{i:010d}",
                "symbol": f"S{i}",
                "signal_available_date": "2023-06-01",
                "excess_return_1q": 0.01 * (i % 5) - 0.02,
                "market_cap_asof": 1e9 + i * 1e8,
                "liquidity_proxy_json": {"avg_daily_volume": 1e6 + i},
            }
        )
    scores = []
    for i in range(30):
        scores.append(
            {
                "cik": f"{i:010d}",
                "as_of_date": "2023-06-01",
                "state_change_score_v1": float(i % 7) * 0.1,
                "missing_component_count": i % 3,
            }
        )

    client = MagicMock()

    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_research_hypothesis",
        lambda c, hypothesis_id: {
            "id": hypothesis_id,
            "program_id": "p1",
            "status": "candidate_recipe",
            "feature_definition_json": {"families": ["liquidity_proxy"]},
        },
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_research_reviews_for_hypothesis",
        lambda c, hypothesis_id: [{"id": "r1"}],
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_research_program",
        lambda c, program_id: {
            "id": program_id,
            "universe_name": "u1",
            "linked_quality_context_json": {"quality_class": "thin_input"},
        },
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_public_core_cycle_quality_run_by_id",
        lambda c, rid: {"state_change_run_id": "sc1"},
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_latest_state_change_run_id",
        lambda c, universe_name: "sc1",
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_max_as_of_universe",
        lambda c, universe_name: "2024-01-01",
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_symbols_universe_as_of",
        lambda c, universe_name, as_of_date: ["S0"],
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_factor_market_validation_panels_for_symbols",
        lambda c, symbols, limit: panels,
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_state_change_scores_for_run",
        lambda c, run_id, limit: scores,
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.fetch_research_residual_links_for_hypothesis",
        lambda c, hypothesis_id: [],
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.insert_recipe_validation_run",
        lambda c, row: "run-1",
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.insert_recipe_validation_results_batch",
        lambda c, rows: None,
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.insert_recipe_validation_comparisons_batch",
        lambda c, rows: None,
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.insert_recipe_survival_decision",
        lambda c, row: "surv-1",
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.insert_recipe_failure_cases_batch",
        _capture_failures,
    )
    monkeypatch.setattr(
        "research_validation.service.dbrec.update_recipe_validation_run",
        lambda c, run_id, patch: None,
    )

    out = run_recipe_validation(client, hypothesis_id="h1", panel_limit=100)
    assert out.get("ok") is True
    assert "failures" in captured
    assert any(
        f.get("failure_reason") == "thin_input_program_context_dependence"
        for f in captured["failures"]
    )


def test_min_sample_rows_constant_sane() -> None:
    assert MIN_SAMPLE_ROWS >= 12


def test_state_change_pick_at_or_before_signal() -> None:
    scores = [
        {"cik": "0000320193", "as_of_date": "2024-01-10", "state_change_score_v1": 1.0},
        {"cik": "0000320193", "as_of_date": "2024-03-01", "state_change_score_v1": 2.0},
    ]
    by_cik = state_change_rows_by_cik_sorted(scores)
    r = pick_state_change_at_or_before_signal(
        by_cik, cik="320193", signal_date="2024-02-15"
    )
    assert r is not None
    assert str(r.get("as_of_date"))[:10] == "2024-01-10"


def test_cli_rejects_non_uuid_hypothesis_id(capsys: pytest.CaptureFixture[str]) -> None:
    from main import _exit_unless_uuid

    assert _exit_unless_uuid("hypothesis_id", "YOUR_HYPOTHESIS_UUID") == 1
    out = capsys.readouterr().out
    assert "invalid_uuid" in out
    assert _exit_unless_uuid("hypothesis_id", "550e8400-e29b-41d4-a716-446655440000") is None
