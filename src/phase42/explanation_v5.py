"""Explanation surface v5 — evidence accumulation, discrimination, narrowing, gate (no auto-promotion)."""

from __future__ import annotations

from typing import Any


def render_phase42_explanation_v5_md(*, bundle: dict[str, Any]) -> str:
    gate = bundle.get("promotion_gate_phase42") or {}
    score = bundle.get("family_evidence_scorecard") or {}
    disc = bundle.get("discrimination_summary") or {}
    narrow = bundle.get("hypothesis_narrowing") or {}
    p43 = bundle.get("phase43") or {}
    digest = bundle.get("stable_run_digest") or ""

    lines = [
        "# Research explanation (Phase 42 v5)",
        "",
        "_Human judgment only. **Not** investment advice; no buy/sell/hold recommendation._",
        "",
        "## Evidence scorecard (cohort A)",
        "",
        f"- **cohort_row_count**: `{score.get('cohort_row_count')}`",
        f"- **filing_blocker_distribution**: `{score.get('filing_blocker_distribution')}`",
        f"- **sector_blocker_distribution**: `{score.get('sector_blocker_distribution')}`",
        f"- **outcome_discriminating_family_count**: `{score.get('outcome_discriminating_family_count')}`",
        "",
        "## Outcome discrimination (Phase 41 family rollups)",
        "",
        f"- **any_family_outcome_discriminating**: `{disc.get('any_family_outcome_discriminating')}`",
        f"- **live_and_discriminating_family_ids**: `{disc.get('live_and_discriminating_family_ids')}`",
        f"- **families_with_identical_rollups_groups**: `{disc.get('families_with_identical_rollups_groups')}`",
        "",
        "## Hypothesis narrowing (labels only)",
        "",
        f"- **headline**: `{narrow.get('headline')}`",
        f"- **by_family_id**: `{narrow.get('by_family_id')}`",
        "",
        "## Promotion gate (v4 context, Phase 42)",
        "",
        f"- **gate_status**: `{gate.get('gate_status')}`",
        f"- **primary_block_category**: `{gate.get('primary_block_category')}`",
        f"- **blocking_reasons**: `{gate.get('blocking_reasons')}`",
        f"- **phase42_context**: `{gate.get('phase42_context')}`",
        "",
        "## Run digest",
        "",
        f"- **stable_run_digest**: `{digest}`",
        "",
        "## Phase 43 (recommended next)",
        "",
        f"- **`{p43.get('phase43_recommendation')}`**",
        f"- {p43.get('rationale', '')}",
        "",
    ]
    return "\n".join(lines)
