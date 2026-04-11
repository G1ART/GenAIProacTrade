"""Explanation surface v6 — bounded backfill truthfulness + retest deltas."""

from __future__ import annotations

from typing import Any


def render_phase43_explanation_v6_md(*, bundle: dict[str, Any]) -> str:
    ba = bundle.get("before_after_row_audit") or []
    p41 = bundle.get("phase41_rerun_after_backfill") or {}
    p42 = bundle.get("phase42_rerun_after_backfill") or {}
    p44 = bundle.get("phase44") or {}
    bf = bundle.get("backfill_actions") or {}

    lines = [
        "# Research explanation (Phase 43 v6 — bounded falsifier substrate backfill)",
        "",
        "_Judgment support only. Not investment advice; no buy/sell/hold._",
        "",
        "## What ran",
        "",
        "- **Cohort**: exactly 8 rows from Phase 42 Supabase-fresh `row_level_blockers` (no universe expansion).",
        "- **Filing**: bounded `run_sample_ingest` per distinct CIK (capped).",
        "- **Sector**: `run_market_metadata_hydration_for_symbols` for those 8 symbols only.",
        "- **Retest**: Phase 41 two families again, then Phase 42 with **Supabase-fresh** blockers (authoritative).",
        "",
        "## Backfill actions (summary)",
        "",
        f"- **filing**: `{bf.get('filing')}`",
        f"- **sector**: `{bf.get('sector')}`",
        "",
        "## Scorecard (Phase 42 family evidence)",
        "",
        f"- **before**: `{bundle.get('scorecard_before')}`",
        f"- **after**: `{bundle.get('scorecard_after')}`",
        f"- **stable_run_digest**: `{bundle.get('stable_run_digest_before')}` → `{bundle.get('stable_run_digest_after')}`",
        "",
        "## Gate (Phase 42 payload)",
        "",
        f"- **before** `primary_block_category`: `{ (bundle.get('gate_before') or {}).get('primary_block_category')}`",
        f"- **after** `primary_block_category`: `{ (bundle.get('gate_after') or {}).get('primary_block_category')}`",
        "",
        "## Before/after rows (abbrev)",
        "",
        f"- `{len(ba)}` rows — see `phase43_targeted_substrate_before_after_audit.md` for full tables.",
        "",
        "## Phase 41 rerun (after backfill)",
        "",
        f"- **ok**: `{p41.get('ok')}`",
        f"- **experiment_id**: `{ (p41.get('pit_execution') or {}).get('experiment_id')}`",
        "",
        "## Phase 42 rerun (authoritative)",
        "",
        f"- **ok**: `{p42.get('ok')}`",
        f"- **phase42_used_supabase_fresh**: `{bundle.get('phase42_rerun_used_supabase_fresh')}`",
        "",
        "## Phase 44 (recommended next)",
        "",
        f"- **`{p44.get('phase44_recommendation')}`**",
        f"- {p44.get('rationale', '')}",
        "",
    ]
    return "\n".join(lines)
