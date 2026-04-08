"""Phase 30 번들용 검증·분기 스냅샷 기판 스냅샷."""

from __future__ import annotations

from typing import Any

from phase28.factor_materialization import report_factor_panel_materialization_gaps
from phase29.quarter_snapshot_gaps import report_quarter_snapshot_backfill_gaps
from public_depth.diagnostics import compute_substrate_coverage
from targeted_backfill.market_metadata_gaps import report_market_metadata_gap_drivers
from targeted_backfill.validation_registry import (
    registry_gap_rollup_for_bundle,
    report_validation_registry_gaps,
)


def collect_validation_substrate_snapshot(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
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
    rollup = registry_gap_rollup_for_bundle(reg.get("registry_bucket_counts"))
    factor_missing = int(
        (reg.get("registry_bucket_counts") or {}).get(
            "factor_panel_missing_for_resolved_cik", 0
        )
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
        "registry_gap_rollup": rollup,
        "factor_panel_missing_for_resolved_cik": factor_missing,
        "missing_quarter_snapshot_for_cik": mcount,
        "quarter_snapshot_classification_counts": qrep.get("classification_counts"),
    }
