"""메타 수화(Phase 27 경로) + 팩터/검증 물질화 수리를 한 번에 실행."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from public_depth.diagnostics import compute_substrate_coverage
from targeted_backfill.market_metadata_gaps import (
    report_market_metadata_gap_drivers,
    run_market_metadata_hydration_repair,
)
from targeted_backfill.validation_registry import (
    registry_gap_rollup_for_bundle,
    report_validation_registry_gaps,
)

from phase28.factor_materialization import (
    report_factor_panel_materialization_gaps,
    run_factor_panel_materialization_repair,
)


def run_phase28_provider_metadata_and_panel_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_factor_cik_repairs: int = 40,
    max_validation_cik_repairs: int = 40,
) -> dict[str, Any]:
    client = get_supabase_client(settings)

    cov_b, ex_b = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    meta_drv_b = report_market_metadata_gap_drivers(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    reg_b = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rollup_b = registry_gap_rollup_for_bundle(reg_b.get("registry_bucket_counts"))

    meta_rep = run_market_metadata_hydration_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    fac_rep = run_factor_panel_materialization_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_factor_cik_repairs=max_factor_cik_repairs,
        max_validation_cik_repairs=max_validation_cik_repairs,
    )
    mat_report = report_factor_panel_materialization_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    meta_drv_a = report_market_metadata_gap_drivers(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    cov_a, ex_a = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    reg_a = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rollup_a = registry_gap_rollup_for_bundle(reg_a.get("registry_bucket_counts"))

    return {
        "ok": True,
        "universe_name": universe_name,
        "before": {
            "joined_recipe_substrate_row_count": cov_b.get(
                "joined_recipe_substrate_row_count"
            ),
            "joined_market_metadata_flagged_count": meta_drv_b.get(
                "joined_market_metadata_flagged_count"
            ),
            "thin_input_share": cov_b.get("thin_input_share"),
            "exclusion_distribution": ex_b,
            "registry_gap_rollup": rollup_b,
            "missing_validation_symbol_count": reg_b.get("missing_symbol_count"),
        },
        "after": {
            "joined_recipe_substrate_row_count": cov_a.get(
                "joined_recipe_substrate_row_count"
            ),
            "joined_market_metadata_flagged_count": meta_drv_a.get(
                "joined_market_metadata_flagged_count"
            ),
            "thin_input_share": cov_a.get("thin_input_share"),
            "exclusion_distribution": ex_a,
            "registry_gap_rollup": rollup_a,
            "missing_validation_symbol_count": reg_a.get("missing_symbol_count"),
        },
        "market_metadata_hydration_repair": meta_rep,
        "factor_materialization_repair": fac_rep,
        "factor_materialization_report_latest": {
            "materialization_bucket_counts": mat_report.get(
                "materialization_bucket_counts"
            ),
        },
    }
