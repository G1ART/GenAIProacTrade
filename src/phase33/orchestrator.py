"""Phase 33 orchestration: truth audit, price gaps, forward retry, GIS, bundle."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase28.factor_materialization import report_factor_panel_materialization_gaps
from phase29.quarter_snapshot_gaps import report_quarter_snapshot_backfill_gaps
from phase33.forward_retry_after_price import run_forward_return_retry_after_price_repair
from phase33.gis_narrow import inspect_gis_raw_present_no_silver_deterministic
from phase33.metric_truth_audit import report_forward_metric_truth_audit
from phase33.metrics import collect_phase33_substrate_snapshot
from phase33.phase32_bundle_io import load_phase32_bundle
from phase33.phase34_recommend import recommend_phase34_after_phase33
from phase33.price_coverage import (
    report_price_coverage_gaps_for_forward,
    run_price_coverage_backfill_for_forward,
)
from targeted_backfill.validation_registry import report_validation_registry_gaps


def run_phase33_forward_coverage_truth(
    settings: Any,
    *,
    universe_name: str,
    phase32_bundle_path: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    bundle32 = load_phase32_bundle(phase32_bundle_path)

    before = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    metric_truth_start = report_forward_metric_truth_audit(
        client,
        universe_name=universe_name,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
    )

    price_gap_report = report_price_coverage_gaps_for_forward(
        client,
        phase32_bundle=bundle32,
        price_lookahead_days=price_lookahead_days,
    )

    price_backfill = run_price_coverage_backfill_for_forward(
        settings,
        client,
        phase32_bundle=bundle32,
        price_lookahead_days=price_lookahead_days,
    )

    forward_retry = run_forward_return_retry_after_price_repair(
        settings,
        universe_name=universe_name,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    after = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    metric_truth_after = forward_retry.get("metric_truth_after") or metric_truth_start

    reg = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    mat = report_factor_panel_materialization_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=reg,
    )
    qrep = report_quarter_snapshot_backfill_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=reg,
        materialization_report=mat,
    )

    gis_out = inspect_gis_raw_present_no_silver_deterministic(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    j0 = int(before.get("joined_recipe_substrate_row_count") or 0)
    j1 = int(after.get("joined_recipe_substrate_row_count") or 0)
    fb = forward_retry.get("forward_build") or {}

    stage_semantics_truth = {
        "forward_row_unblocked_now_count": int(fb.get("success_operations") or 0),
        "forward_row_unblocked_note": "forward_returns upsert ops (next_month+next_quarter per panel row)",
        "symbol_cleared_from_missing_excess_queue_count": int(
            metric_truth_after.get("symbol_cleared_from_missing_excess_queue_count")
            or 0
        ),
        "joined_recipe_unlocked_now_count": j1 - j0,
        "price_coverage_repaired_now_count": int(
            price_backfill.get("price_coverage_repaired_now_count") or 0
        ),
        "validation_panel_excess_null_rows_touched_set_live": (
            metric_truth_after.get("validation_panel_rows_for_touched_symbols") or {}
        ).get("excess_null_row_count"),
    }

    phase34 = recommend_phase34_after_phase33(
        before=before,
        after=after,
        price_backfill=price_backfill,
        forward_retry=forward_retry,
        metric_truth_after=metric_truth_after,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase32_bundle_path": phase32_bundle_path,
        "before": before,
        "after": after,
        "quarter_snapshot_classification_counts_after": qrep.get("classification_counts"),
        "metric_truth_audit_start": metric_truth_start,
        "price_coverage_gap_report": price_gap_report,
        "price_coverage_backfill": price_backfill,
        "forward_return_retry_after_price_repair": forward_retry,
        "metric_truth_audit_after": metric_truth_after,
        "gis_deterministic_inspect": gis_out,
        "stage_semantics_truth": stage_semantics_truth,
        "phase34": phase34,
    }
