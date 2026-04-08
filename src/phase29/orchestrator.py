"""Phase 29: 메타 수화 → 검증 갱신 → 분기 스냅샷 → 팩터 물질화."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase28.factor_materialization import (
    report_factor_panel_materialization_gaps,
    run_factor_panel_materialization_repair,
)
from phase29.phase30_recommend import recommend_phase30_branch
from phase29.quarter_snapshot_gaps import (
    report_quarter_snapshot_backfill_gaps,
    run_quarter_snapshot_backfill_repair,
)
from phase29.stale_validation_metadata import (
    run_validation_refresh_after_metadata_hydration,
)
from public_depth.diagnostics import compute_substrate_coverage
from targeted_backfill.market_metadata_gaps import (
    report_market_metadata_gap_drivers,
    run_market_metadata_hydration_repair,
)
from targeted_backfill.validation_registry import (
    registry_gap_rollup_for_bundle,
    report_validation_registry_gaps,
)


def run_phase29_validation_refresh_and_snapshot_backfill(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_validation_rebuilds: int = 800,
    max_quarter_snapshot_cik_repairs: int = 25,
    max_factor_cik_repairs: int = 40,
    max_validation_cik_repairs: int = 40,
) -> dict[str, Any]:
    client = get_supabase_client(settings)

    def _snap(*, phase: str) -> dict[str, Any]:
        if phase == "before":
            print("phase29_snapshot_before_started", flush=True)
        else:
            print("phase29_snapshot_after_started", flush=True)
        cov, excl = compute_substrate_coverage(
            client, universe_name=universe_name, panel_limit=panel_limit
        )
        meta_drv = report_market_metadata_gap_drivers(
            client,
            universe_name=universe_name,
            panel_limit=panel_limit,
            price_lookahead_days=price_lookahead_days,
        )
        reg = report_validation_registry_gaps(
            client, universe_name=universe_name, panel_limit=panel_limit
        )
        if phase == "before":
            print("phase29_snapshot_before_validation_registry_done", flush=True)
        else:
            print("phase29_snapshot_after_validation_registry_done", flush=True)
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
        mcount = int(
            (mat.get("materialization_bucket_counts") or {}).get(
                "missing_quarter_snapshot_for_cik",
                0,
            )
        )
        return {
            "joined_recipe_substrate_row_count": cov.get(
                "joined_recipe_substrate_row_count"
            ),
            "joined_market_metadata_flagged_count": meta_drv.get(
                "joined_market_metadata_flagged_count"
            ),
            "thin_input_share": cov.get("thin_input_share"),
            "exclusion_distribution": dict(excl),
            "missing_validation_symbol_count": reg.get("missing_symbol_count"),
            "registry_gap_rollup": registry_gap_rollup_for_bundle(
                reg.get("registry_bucket_counts")
            ),
            "missing_quarter_snapshot_for_cik": mcount,
            "quarter_snapshot_classification_counts": qrep.get(
                "classification_counts"
            ),
        }

    before = _snap(phase="before")

    meta_rep = run_market_metadata_hydration_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    print("phase29_metadata_hydration_done", flush=True)
    stale_rep = run_validation_refresh_after_metadata_hydration(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_rebuilds=max_validation_rebuilds,
    )
    print("phase29_stale_validation_refresh_done", flush=True)
    q_rep = run_quarter_snapshot_backfill_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_quarter_snapshot_cik_repairs,
    )
    print("phase29_quarter_snapshot_backfill_done", flush=True)
    fac_rep = run_factor_panel_materialization_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_factor_cik_repairs=max_factor_cik_repairs,
        max_validation_cik_repairs=max_validation_cik_repairs,
    )
    print("phase29_factor_materialization_done", flush=True)

    after = _snap(phase="after")
    cleared = int(
        stale_rep.get("validation_metadata_flags_cleared_count") or 0
    )
    silver_ok = int(q_rep.get("cik_repairs_succeeded") or 0)

    phase30 = recommend_phase30_branch(
        joined_metadata_flagged_after=int(
            after.get("joined_market_metadata_flagged_count") or 0
        ),
        missing_quarter_snapshot_after=int(
            after.get("missing_quarter_snapshot_for_cik") or 0
        ),
        missing_validation_after=int(
            after.get("missing_validation_symbol_count") or 0
        ),
        validation_flags_cleared=cleared,
        thin_input_share_after=after.get("thin_input_share"),
        silver_materialization_repair_succeeded=silver_ok,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "before": before,
        "after": after,
        "market_metadata_hydration_repair": meta_rep,
        "stale_validation_refresh": stale_rep,
        "quarter_snapshot_backfill_repair": q_rep,
        "factor_materialization_repair": fac_rep,
        "phase30": phase30,
    }
