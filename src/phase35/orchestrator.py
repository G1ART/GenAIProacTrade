"""Phase 35 orchestrator: displacement, join gaps, maturity, price, state_change, GIS, bundle."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase33.gis_narrow import inspect_gis_raw_present_no_silver_deterministic
from phase33.metrics import collect_phase33_substrate_snapshot
from phase34.price_backfill import run_bounded_price_ingest_for_propagation_missing_windows
from phase35.join_displacement import report_forward_validation_join_displacement
from phase35.matured_window_schedule import (
    report_matured_window_schedule_for_forward,
    run_matured_window_forward_retry_for_phase34_immature,
)
from phase35.phase34_bundle_io import load_phase34_bundle
from phase35.phase36_recommend import recommend_phase36_after_phase35
from phase35.state_change_join_gaps import report_state_change_join_gaps_after_phase34
from phase35.state_change_refresh import run_state_change_join_refresh_after_phase34

PHASE34_IMMATURE_SYMBOLS = (
    "MCK",
    "MDT",
    "MKC",
    "MU",
    "NDSN",
    "NTAP",
    "NWSA",
)


def run_phase35_join_displacement_and_maturity(
    settings: Any,
    *,
    universe_name: str,
    phase34_bundle_path: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    bundle34 = load_phase34_bundle(phase34_bundle_path)

    before = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    displacement_initial = report_forward_validation_join_displacement(
        client,
        universe_name=universe_name,
        phase34_bundle=bundle34,
    )
    join_gaps = report_state_change_join_gaps_after_phase34(
        client,
        universe_name=universe_name,
        phase34_bundle=bundle34,
    )

    matured_schedule = report_matured_window_schedule_for_forward(
        client,
        phase34_bundle=bundle34,
        price_lookahead_days=price_lookahead_days,
        expected_symbols=PHASE34_IMMATURE_SYMBOLS,
    )

    matured_retry = run_matured_window_forward_retry_for_phase34_immature(
        settings,
        phase34_bundle=bundle34,
        price_lookahead_days=price_lookahead_days,
    )

    gap_final = bundle34.get("propagation_gap_final") or {}
    price_out = run_bounded_price_ingest_for_propagation_missing_windows(
        settings,
        client,
        propagation_gap_report=gap_final,
        price_lookahead_days=price_lookahead_days,
    )

    refresh_out = run_state_change_join_refresh_after_phase34(
        settings,
        universe_name=universe_name,
        phase34_bundle=bundle34,
    )

    after = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    displacement_final = report_forward_validation_join_displacement(
        client,
        universe_name=universe_name,
        phase34_bundle=bundle34,
    )

    gis_out = inspect_gis_raw_present_no_silver_deterministic(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    hyp = (
        displacement_final.get("hypothesis_phase34_excess_to_no_state_change_join") or {}
    )
    hyp_supported = bool(hyp.get("supported_by_counts"))

    phase36 = recommend_phase36_after_phase35(
        before=before,
        after=after,
        displacement_hypothesis_supported=hyp_supported,
        refresh_out=refresh_out,
        matured_schedule=matured_schedule,
    )

    j0 = int(before.get("joined_recipe_substrate_row_count") or 0)
    j1 = int(after.get("joined_recipe_substrate_row_count") or 0)
    nsc0 = int(
        (before.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
    )
    nsc1 = int(
        (after.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
    )

    c34 = bundle34.get("closeout_summary") or {}
    disp0 = displacement_initial.get("displacement_counts") or {}
    disp1 = displacement_final.get("displacement_counts") or {}

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
        "no_state_change_join": nsc1,
        "validation_excess_filled_now_count": int(
            c34.get("validation_excess_filled_now_count") or 0
        ),
        "symbol_cleared_from_missing_excess_queue_count": int(
            c34.get("symbol_cleared_from_missing_excess_queue_count") or 0
        ),
        "joined_recipe_unlocked_now_count": j1 - j0,
        "no_state_change_join_cleared_count": max(0, nsc0 - nsc1),
        "displacement_synchronized_set_initial": disp0,
        "displacement_synchronized_set_final": disp1,
        "matured_eligible_now_count": int(
            matured_schedule.get("matured_eligible_now_count") or 0
        ),
        "still_not_matured_count": int(
            matured_schedule.get("still_not_matured_count") or 0
        ),
        "matured_forward_retry_success_count": int(
            matured_retry.get("matured_forward_retry_success_count") or 0
        ),
        "price_coverage_repaired_now_count": int(
            price_out.get("price_coverage_repaired_now_count") or 0
        ),
        "gis_outcome": gis_out.get("outcome"),
        "gis_blocked_reason": gis_out.get("blocked_reason"),
        "phase36": phase36,
    }

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase34_bundle_path": phase34_bundle_path,
        "before": before,
        "after": after,
        "forward_validation_join_displacement_initial": displacement_initial,
        "state_change_join_gaps": join_gaps,
        "matured_window_schedule": matured_schedule,
        "matured_window_forward_retry": matured_retry,
        "price_backfill_propagation_missing_window": price_out,
        "state_change_join_refresh": refresh_out,
        "forward_validation_join_displacement_final": displacement_final,
        "gis_deterministic_inspect": gis_out,
        "closeout_summary": summary,
        "phase36": phase36,
    }
