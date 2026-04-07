"""Operator closure artifact: thin_input_root_cause_review.md (Phase 26)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thin_input_root_cause.phase27 import classify_phase27_next_move


def build_review_bundle(
    client: Any,
    *,
    universe_name: str,
    program_id_raw: str | None,
    panel_limit: int,
    quality_run_lookback: int,
) -> dict[str, Any]:
    from thin_input_root_cause.decompose import rank_leverageable_blocker, report_thin_input_drivers
    from thin_input_root_cause.effectiveness import (
        report_forward_backfill_effectiveness,
        report_state_change_repair_effectiveness,
        report_validation_repair_effectiveness,
    )
    from thin_input_root_cause.policy_trace import (
        report_quality_threshold_sensitivity_for_universe,
    )

    dec = report_thin_input_drivers(
        client,
        universe_name=universe_name,
        program_id_raw=program_id_raw,
        panel_limit=panel_limit,
        quality_run_lookback=quality_run_lookback,
    )
    eff_v = report_validation_repair_effectiveness(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    eff_f = report_forward_backfill_effectiveness(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    eff_s = report_state_change_repair_effectiveness(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    sens = report_quality_threshold_sensitivity_for_universe(
        client,
        universe_name=universe_name,
        quality_run_lookback=quality_run_lookback,
    )

    leverage = rank_leverageable_blocker(dec)
    noop_all = (
        bool(eff_v.get("likely_no_op"))
        and bool(eff_f.get("likely_no_op"))
    )
    joined_n = int(dec.get("joined_substrate_row_count") or 0)
    clean_joined = (
        dec.get("joined_substrate_driver_counts") or {}
    ).get("joined_panel_json_clean_no_quality_flags", 0)
    primary = "mixed"
    if leverage.startswith("no_validation"):
        primary = "data_absence"
    elif leverage.startswith("missing_excess"):
        primary = "data_absence"
    elif leverage.startswith("no_state_change"):
        primary = "join_logic"
    if dec.get("cycle_thin_driver_counts"):
        primary = "quality_policy" if joined_n > 0 and int(clean_joined or 0) == joined_n else primary

    thin = dec.get("substrate_metrics", {}).get("thin_input_share")
    rerun = dec.get("rerun_readiness") or {}
    p27 = classify_phase27_next_move(
        recommend_rerun_phase15=bool(rerun.get("recommend_rerun_phase15")),
        recommend_rerun_phase16=bool(rerun.get("recommend_rerun_phase16")),
        primary_blocker_category=primary,
        generic_substrate_sprint_likely_wasteful=noop_all,
        thin_input_share=float(thin) if isinstance(thin, (int, float)) else None,
        joined_substrate_rows=joined_n,
    )

    return {
        "decomposition": dec,
        "effectiveness_validation": eff_v,
        "effectiveness_forward": eff_f,
        "effectiveness_state_change": eff_s,
        "threshold_sensitivity": sens,
        "primary_blocker_category": primary,
        "leverageable_exclusion": leverage,
        "phase27": p27,
        "premium_auto_open": False,
        "production_scoring_boundary": (
            "thin_input_root_cause 는 진단·보내기만 수행; 프로덕션 스코어링 경로를 변경하지 않음."
        ),
    }


def write_thin_input_root_cause_review_md(
    *,
    path: str | Path,
    bundle: dict[str, Any],
) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    dec = bundle.get("decomposition") or {}
    ev = bundle.get("effectiveness_validation") or {}
    ef = bundle.get("effectiveness_forward") or {}
    es = bundle.get("effectiveness_state_change") or {}
    sens = bundle.get("threshold_sensitivity") or {}
    p27 = bundle.get("phase27") or {}

    lines = [
        "# Thin-input root cause review (Phase 26)",
        "",
        f"- UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Universe: `{dec.get('universe_name')}`",
        "",
        "## Why thin_input_share can stay 1.0",
        "",
        dec.get("cycle_quality_note", ""),
        "",
        "### Cycle-quality drivers (public_core_cycle_quality_runs, thin_input only)",
        "",
        f"- Counts: `{dec.get('cycle_thin_driver_counts')}`",
        f"- Thin runs in lookback: {dec.get('thin_input_quality_runs_in_lookback')}",
        "",
        "### Joined substrate row flags (recipe-joined panels)",
        "",
        f"- Joined rows: {dec.get('joined_substrate_row_count')}",
        f"- Driver counts: `{dec.get('joined_substrate_driver_counts')}`",
        "",
        "## Phase 25 repair effectiveness (zero-delta audit)",
        "",
        "### Validation panel repair",
        "",
        f"- Targets (panel rows): {ev.get('targets_identified_panel_rows')}",
        f"- Likely no-op: `{ev.get('likely_no_op')}`",
        f"- Current no_validation_panel rows: {ev.get('current_no_validation_panel_exclusion_rows')}",
        "",
        "### Forward backfill",
        "",
        f"- Targets: {ef.get('targets_identified_panel_rows')}",
        f"- Likely no-op: `{ef.get('likely_no_op')}`",
        f"- Current missing_excess rows: {ef.get('current_missing_excess_exclusion_rows')}",
        "",
        "### State-change engine",
        "",
        f"- Current no_state_change_join rows: {es.get('current_no_state_change_join_exclusion_rows')}",
        f"- Note: {es.get('note')}",
        "",
        "## Quality threshold sensitivity (review-only)",
        "",
        "```json",
        json.dumps(sens, indent=2, ensure_ascii=False, default=str)[:8000],
        "```",
        "",
        "## Primary blocker & Phase 27",
        "",
        f"- **Primary blocker category**: `{bundle.get('primary_blocker_category')}`",
        f"- **Top exclusion lever**: `{bundle.get('leverageable_exclusion')}`",
        f"- **Phase 27 recommendation**: `{p27.get('phase27_recommendation')}`",
        f"- **Rationale**: {p27.get('rationale')}",
        "",
        "## Another broad substrate sprint?",
        "",
        "If all Phase 25 paths show `likely_no_op: true` and exclusions are unchanged, "
        "**another generic sprint is likely wasteful** until the bounded blocker set (exports) is addressed.",
        "",
        "## Boundaries",
        "",
        str(bundle.get("production_scoring_boundary")),
        "- **Premium auto-open**: false (public-first default).",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
