"""Phase 32 오케스트레이션 — forward 백필·silver 스냅·GIS·raw 재시도."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase32.forward_return_phase31 import (
    report_forward_return_gap_targets_after_phase31,
    run_forward_return_backfill_for_phase31_touched,
)
from phase32.metrics import collect_phase32_substrate_snapshot
from phase32.phase31_bundle_io import (
    load_phase31_bundle,
    phase31_downstream_unblocked_ciks,
)
from phase32.phase33_recommend import recommend_phase33_after_phase32
from phase32.raw_deferred_retry import retry_raw_facts_deferred_from_phase31_bundle
from phase32.silver_snapshot_cleanup import (
    run_gis_raw_present_no_silver_repair,
    run_silver_present_snapshot_materialization_repair,
)


def run_phase32_forward_unlock_and_snapshot_cleanup(
    settings: Any,
    *,
    universe_name: str,
    phase31_bundle_path: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_forward_target_ciks: int = 30,
    max_silver_snapshot_cik_repairs: int = 15,
    max_raw_deferred_rows: int = 20,
) -> dict[str, Any]:
    bundle31 = load_phase31_bundle(phase31_bundle_path)
    client = get_supabase_client(settings)

    before = collect_phase32_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    forward_gap_report = report_forward_return_gap_targets_after_phase31(
        client,
        bundle=bundle31,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_target_ciks=max_forward_target_ciks,
    )

    forward_backfill = run_forward_return_backfill_for_phase31_touched(
        settings,
        bundle=bundle31,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
        max_target_ciks=max_forward_target_ciks,
    )

    silver_snapshot_repair = run_silver_present_snapshot_materialization_repair(
        settings,
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_silver_snapshot_cik_repairs,
    )

    gis_repair = run_gis_raw_present_no_silver_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
    )

    raw_deferred_retry = retry_raw_facts_deferred_from_phase31_bundle(
        settings,
        bundle=bundle31,
        max_rows=max_raw_deferred_rows,
    )

    after = collect_phase32_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    p31_val_n = len(phase31_downstream_unblocked_ciks(bundle31))
    stage_transitions = {
        "phase31_reference": {
            "bundle_path": phase31_bundle_path,
            "validation_unblocked_cik_count_in_phase31": p31_val_n,
        },
        "forward_return_unlocked_now_count": int(
            forward_backfill.get("repaired_to_forward_present") or 0
        ),
        "quarter_snapshot_materialized_now_count": int(
            silver_snapshot_repair.get("snapshot_materialized_now_count") or 0
        ),
        "downstream_cascade_cik_runs_after_snapshot_repair": sum(
            len((a.get("downstream_cascade") or {}).get("per_cik") or [])
            for a in (silver_snapshot_repair.get("actions") or [])
            if not a.get("skipped")
        ),
        "factor_materialized_now_count": sum(
            1
            for a in (silver_snapshot_repair.get("actions") or [])
            if not a.get("skipped")
        ),
        "validation_panel_refreshed_count": sum(
            1
            for a in (silver_snapshot_repair.get("actions") or [])
            if not a.get("skipped")
        ),
        "downstream_cascade_cik_runs_after_snapshot_repair": sum(
            len((a.get("downstream_cascade") or {}).get("per_cik") or [])
            for a in (silver_snapshot_repair.get("actions") or [])
            if not a.get("skipped")
        ),
        "gis_seam_actions_count": len((gis_repair.get("actions") or [])),
        "raw_facts_recovered_on_retry_count": int(
            (raw_deferred_retry.get("outcome_summary") or {}).get(
                "recovered_on_retry", 0
            )
        ),
    }

    phase33 = recommend_phase33_after_phase32(
        before=before,
        after=after,
        forward_backfill=forward_backfill,
        silver_snapshot_repair=silver_snapshot_repair,
        raw_deferred_retry=raw_deferred_retry,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase31_bundle_path": phase31_bundle_path,
        "before": before,
        "after": after,
        "forward_gap_report_phase31_touched": forward_gap_report,
        "forward_return_backfill_phase31_touched": forward_backfill,
        "silver_present_snapshot_materialization_repair": silver_snapshot_repair,
        "gis_raw_present_no_silver_repair": gis_repair,
        "raw_facts_deferred_retry": raw_deferred_retry,
        "stage_transitions": stage_transitions,
        "phase33": phase33,
    }
