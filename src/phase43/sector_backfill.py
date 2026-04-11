"""Bounded `market_metadata_latest` hydration for cohort symbols only."""

from __future__ import annotations

from typing import Any

from market.price_ingest import run_market_metadata_hydration_for_symbols

from phase43.target_types import CohortTargetRow


def run_bounded_sector_hydration_for_cohort(
    settings: Any,
    *,
    universe_name: str,
    targets: list[CohortTargetRow],
) -> dict[str, Any]:
    symbols = sorted({str(t.get("symbol") or "").upper().strip() for t in targets if t.get("symbol")})
    return run_market_metadata_hydration_for_symbols(
        settings,
        universe_name=universe_name,
        symbols=symbols,
    )
