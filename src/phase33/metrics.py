"""Phase 33 bundle substrate snapshot (same fields as phase32)."""

from __future__ import annotations

from typing import Any

from phase32.metrics import collect_phase32_substrate_snapshot


def collect_phase33_substrate_snapshot(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    return collect_phase32_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
