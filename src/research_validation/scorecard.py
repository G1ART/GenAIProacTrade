"""Deterministic recipe scorecard: JSON + Markdown."""

from __future__ import annotations

from typing import Any


def build_scorecard(
    *,
    hypothesis: dict[str, Any],
    program: dict[str, Any],
    validation_run: dict[str, Any],
    comparisons: list[dict[str, Any]],
    survival: dict[str, Any],
    failure_cases: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    qctx = program.get("linked_quality_context_json") or {}
    premium_hint = "no"
    premium_why = "public_core_only_phase15"
    for fc in failure_cases:
        if (fc.get("premium_overlay_hint") or "").strip():
            premium_hint = "maybe"
            premium_why = "failure_cases_recorded_premium_hints"
            break

    return {
        "recipe_title": hypothesis.get("hypothesis_title"),
        "linked_research_question": program.get("research_question"),
        "economic_rationale": hypothesis.get("economic_rationale"),
        "comparison_baselines": [c.get("baseline_name") for c in comparisons],
        "strongest_positive": summary.get("strongest_positive"),
        "strongest_fragility": summary.get("strongest_fragility"),
        "best_cohort": summary.get("best_cohort"),
        "worst_cohort": summary.get("worst_cohort"),
        "residual_contradiction_count": summary.get("residual_contradiction_count", 0),
        "quality_context_dependence": {
            "program_quality_class": qctx.get("quality_class"),
            "quality_run_id": qctx.get("public_core_cycle_quality_run_id"),
        },
        "survival_decision": survival.get("survival_status"),
        "survival_rationale": survival.get("rationale"),
        "fragility_json": survival.get("fragility_json"),
        "premium_overlay_likely_helpful": premium_hint,
        "premium_overlay_rationale": premium_why,
        "validation_run_id": str(validation_run.get("id")),
        "feature_families": (hypothesis.get("feature_definition_json") or {}).get(
            "families"
        ),
    }


def render_scorecard_markdown(card: dict[str, Any]) -> str:
    lines = [
        "# Recipe validation scorecard",
        "",
        f"**Recipe**: {card.get('recipe_title')}",
        f"**Research question**: {card.get('linked_research_question')}",
        "",
        "## Economic rationale",
        str(card.get("economic_rationale") or "")[:2000],
        "",
        "## Baselines compared",
        ", ".join(str(x) for x in (card.get("comparison_baselines") or [])),
        "",
        "## Results snapshot",
        f"- Strongest positive: `{card.get('strongest_positive')}`",
        f"- Strongest fragility: `{card.get('strongest_fragility')}`",
        f"- Best cohort (spread): `{card.get('best_cohort')}`",
        f"- Worst cohort (spread): `{card.get('worst_cohort')}`",
        f"- Residual contradiction count: {card.get('residual_contradiction_count')}",
        "",
        "## Quality context",
        f"- Program quality class: `{card.get('quality_context_dependence', {}).get('program_quality_class')}`",
        "",
        "## Survival",
        f"- Status: **{card.get('survival_decision')}**",
        f"- Rationale: {card.get('survival_rationale')}",
        "",
        "## Premium overlay (research hint only)",
        f"- Likely helpful: **{card.get('premium_overlay_likely_helpful')}** — {card.get('premium_overlay_rationale')}",
        "",
        f"*validation_run_id*: `{card.get('validation_run_id')}`",
    ]
    return "\n".join(lines)
