"""Phase 34: 전파 감사 → validation refresh → 성숙 forward 재시도 → 좁은 가격 → GIS → 번들."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase28.factor_materialization import report_factor_panel_materialization_gaps
from phase29.quarter_snapshot_gaps import report_quarter_snapshot_backfill_gaps
from phase33.gis_narrow import inspect_gis_raw_present_no_silver_deterministic
from phase33.metrics import collect_phase33_substrate_snapshot
from phase33.phase32_bundle_io import load_phase32_bundle
from phase34.matured_forward_retry import (
    report_matured_forward_retry_targets,
    run_matured_forward_retry,
)
from phase34.phase35_recommend import recommend_phase35_after_phase34
from phase34.price_backfill import run_bounded_price_ingest_for_propagation_missing_windows
from phase34.propagation_audit import report_forward_validation_propagation_gaps
from phase34.validation_refresh import run_validation_refresh_after_forward_propagation
from targeted_backfill.validation_registry import report_validation_registry_gaps


def run_phase34_forward_validation_propagation(
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

    gap_before = report_forward_validation_propagation_gaps(
        client,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    refresh_out = run_validation_refresh_after_forward_propagation(
        settings,
        client,
        universe_name=universe_name,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    rf_set: set[tuple[str, str, str]] = set()
    for t in refresh_out.get("refresh_failed_keys") or []:
        if isinstance(t, (list, tuple)) and len(t) >= 3:
            rf_set.add((str(t[0]), str(t[1]), str(t[2])))

    gap_after_refresh = report_forward_validation_propagation_gaps(
        client,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
        refresh_failed_keys=rf_set,
    )

    matured_targets = report_matured_forward_retry_targets(
        client,
        phase32_bundle=bundle32,
        price_lookahead_days=price_lookahead_days,
    )

    matured_out = run_matured_forward_retry(
        settings,
        universe_name=universe_name,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    gap_for_price = report_forward_validation_propagation_gaps(
        client,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    price_out = run_bounded_price_ingest_for_propagation_missing_windows(
        settings,
        client,
        propagation_gap_report=gap_for_price,
        price_lookahead_days=price_lookahead_days,
    )

    after = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    final_gap = report_forward_validation_propagation_gaps(
        client,
        phase32_bundle=bundle32,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

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

    mt_b = refresh_out.get("metric_truth_before") or {}
    mt_a = refresh_out.get("metric_truth_after") or {}
    sym_clear_before = int(mt_b.get("symbol_cleared_from_missing_excess_queue_count") or 0)
    sym_clear_after = int(mt_a.get("symbol_cleared_from_missing_excess_queue_count") or 0)

    phase35 = recommend_phase35_after_phase34(
        before=before,
        after=after,
        refresh_out=refresh_out,
        matured_out=matured_out,
        price_out=price_out,
        final_gap=final_gap,
    )

    summary = {
        "joined_recipe_substrate_row_count": j1,
        "thin_input_share": float(after.get("thin_input_share") or 0.0),
        "missing_excess_return_1q": int(after.get("missing_excess_return_1q") or 0),
        "missing_validation_symbol_count": int(
            after.get("missing_validation_symbol_count") or 0
        ),
        "missing_quarter_snapshot_for_cik": int(
            after.get("missing_quarter_snapshot_for_cik") or 0
        ),
        "factor_panel_missing_for_resolved_cik": int(
            after.get("factor_panel_missing_for_resolved_cik") or 0
        ),
        "forward_row_present_count": int(
            final_gap.get("forward_row_present_count") or 0
        ),
        "validation_excess_filled_now_count": int(
            refresh_out.get("validation_excess_filled_now_count") or 0
        ),
        "symbol_cleared_from_missing_excess_queue_count": sym_clear_after,
        "symbol_cleared_from_missing_excess_queue_delta": sym_clear_after
        - sym_clear_before,
        "joined_recipe_unlocked_now_count": j1 - j0,
        "matured_forward_retry_success_count": int(
            matured_out.get("matured_forward_retry_success_count") or 0
        ),
        "still_not_matured_count": int(
            matured_targets.get("still_not_matured_count") or 0
        ),
        "price_coverage_repaired_now_count": int(
            price_out.get("price_coverage_repaired_now_count") or 0
        ),
        "gis_outcome": gis_out.get("outcome"),
        "gis_blocked_reason": gis_out.get("blocked_reason"),
        "phase35": phase35,
    }

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase32_bundle_path": phase32_bundle_path,
        "before": before,
        "after": after,
        "propagation_gap_before": gap_before,
        "propagation_gap_after_refresh": gap_after_refresh,
        "propagation_gap_final": final_gap,
        "validation_refresh": refresh_out,
        "matured_forward_retry_targets": matured_targets,
        "matured_forward_retry": matured_out,
        "price_backfill_propagation_missing_window": price_out,
        "quarter_snapshot_classification_counts_after": qrep.get(
            "classification_counts"
        ),
        "gis_deterministic_inspect": gis_out,
        "closeout_summary": summary,
        "phase35": phase35,
    }
