"""Phase 32 번들용 기판 스냅샷 — `missing_excess_return_1q` 명시."""

from __future__ import annotations

from typing import Any

from phase30.metrics import collect_validation_substrate_snapshot


def collect_phase32_substrate_snapshot(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    snap = collect_validation_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    ex = snap.get("exclusion_distribution") or {}
    snap["missing_excess_return_1q"] = int(ex.get("missing_excess_return_1q") or 0)
    return snap
