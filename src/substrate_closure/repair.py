"""Targeted substrate repairs (Phase 25) — public-first, no premium."""

from __future__ import annotations

from typing import Any

from market.forward_returns_run import run_forward_returns_build_from_rows
from market.validation_panel_run import run_validation_panel_build_from_rows
from substrate_closure.diagnose import (
    collect_panels_for_forward_repair,
    collect_panels_for_validation_repair,
    report_forward_return_gaps,
    report_state_change_join_gaps,
    report_validation_panel_coverage_gaps,
)
from state_change.runner import run_state_change


def run_validation_panel_coverage_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    c = get_supabase_client(settings)
    before = report_validation_panel_coverage_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    miss_before = int(before.get("missing_symbol_count") or 0)
    panels, meta = collect_panels_for_validation_repair(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    build_out: dict[str, Any] = {"skipped": True, "reason": "no_panels_to_build"}
    if panels:
        build_out = run_validation_panel_build_from_rows(
            settings,
            panels=panels,
            metadata_json={
                "substrate_closure": "validation_panel_coverage_repair",
                "universe_name": universe_name,
                **meta,
            },
        )
        build_out["skipped"] = False
    after = report_validation_panel_coverage_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    miss_after = int(after.get("missing_symbol_count") or 0)
    return {
        "ok": True,
        "repair": "validation_panel_coverage",
        "universe_name": universe_name,
        "before": {
            "missing_validation_panel_symbol_count": miss_before,
            "reason_bucket_counts": before.get("reason_bucket_counts"),
        },
        "after": {
            "missing_validation_panel_symbol_count": miss_after,
            "reason_bucket_counts": after.get("reason_bucket_counts"),
        },
        "repaired_panel_input_rows": len(panels),
        "build_result": build_out,
        "tradeoffs": _tradeoff_note(
            primary_improved=miss_after < miss_before,
            primary_label="missing_validation_panel_symbols",
            secondary_checks=[
                (
                    "missing_excess_return_1q",
                    int(before.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0)),
                    int(after.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0)),
                ),
                (
                    "no_state_change_join",
                    int(before.get("exclusion_distribution", {}).get("no_state_change_join", 0)),
                    int(after.get("exclusion_distribution", {}).get("no_state_change_join", 0)),
                ),
            ],
        ),
    }


def run_forward_return_backfill_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    c = get_supabase_client(settings)
    before = report_forward_return_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    ex_before = int(
        before.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0)
    )
    panels, meta = collect_panels_for_forward_repair(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    build_out: dict[str, Any] = {"skipped": True, "reason": "no_forward_gap_panels"}
    if panels:
        build_out = run_forward_returns_build_from_rows(
            settings,
            panels=panels,
            metadata_json={
                "substrate_closure": "forward_return_backfill",
                "universe_name": universe_name,
                **meta,
            },
            price_lookahead_days=price_lookahead_days,
        )
        build_out["skipped"] = False
    after = report_forward_return_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    ex_after = int(after.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0))
    return {
        "ok": True,
        "repair": "forward_return_backfill",
        "universe_name": universe_name,
        "before": {
            "missing_excess_return_1q_exclusion_rows": ex_before,
            "forward_row_reason_counts": before.get("row_reason_counts"),
        },
        "after": {
            "missing_excess_return_1q_exclusion_rows": ex_after,
            "forward_row_reason_counts": after.get("row_reason_counts"),
        },
        "repaired_panel_input_rows": len(panels),
        "build_result": build_out,
        "tradeoffs": _tradeoff_note(
            primary_improved=ex_after < ex_before,
            primary_label="missing_excess_return_1q",
            secondary_checks=[
                (
                    "no_validation_panel_for_symbol",
                    int(before.get("exclusion_distribution", {}).get("no_validation_panel_for_symbol", 0)),
                    int(after.get("exclusion_distribution", {}).get("no_validation_panel_for_symbol", 0)),
                ),
                (
                    "no_state_change_join",
                    int(before.get("exclusion_distribution", {}).get("no_state_change_join", 0)),
                    int(after.get("exclusion_distribution", {}).get("no_state_change_join", 0)),
                ),
            ],
        ),
    }


def run_state_change_join_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_limit: int = 500,
    factor_version: str = "v1",
) -> dict[str, Any]:
    from db.client import get_supabase_client

    c = get_supabase_client(settings)
    before = report_state_change_join_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    j_before = int(before.get("exclusion_distribution", {}).get("no_state_change_join", 0))
    sc_out = run_state_change(
        c,
        universe_name=universe_name,
        factor_version=factor_version,
        limit=max(1, state_change_limit),
        dry_run=False,
    )
    after = report_state_change_join_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    j_after = int(after.get("exclusion_distribution", {}).get("no_state_change_join", 0))
    return {
        "ok": True,
        "repair": "state_change_join",
        "universe_name": universe_name,
        "before": {
            "no_state_change_join_exclusion_rows": j_before,
            "state_change_run_id": before.get("state_change_run_id"),
        },
        "after": {
            "no_state_change_join_exclusion_rows": j_after,
            "state_change_run_id": after.get("state_change_run_id"),
        },
        "state_change_run_result": sc_out,
        "tradeoffs": _tradeoff_note(
            primary_improved=j_after < j_before,
            primary_label="no_state_change_join",
            secondary_checks=[
                (
                    "no_validation_panel_for_symbol",
                    int(before.get("exclusion_distribution", {}).get("no_validation_panel_for_symbol", 0)),
                    int(after.get("exclusion_distribution", {}).get("no_validation_panel_for_symbol", 0)),
                ),
                (
                    "missing_excess_return_1q",
                    int(before.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0)),
                    int(after.get("exclusion_distribution", {}).get("missing_excess_return_1q", 0)),
                ),
            ],
        ),
    }


def _tradeoff_note(
    *,
    primary_improved: bool,
    primary_label: str,
    secondary_checks: list[tuple[str, int, int]],
) -> dict[str, Any]:
    worsened = [
        {"metric": name, "before": b, "after": a}
        for name, b, a in secondary_checks
        if a > b
    ]
    return {
        "primary_improved": primary_improved,
        "primary_metric": primary_label,
        "secondary_metrics_worsened": worsened,
        "silent_degradation": bool(worsened),
    }
