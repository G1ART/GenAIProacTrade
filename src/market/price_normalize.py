"""raw DailyPriceBar → silver 행(dict). adjusted_close 우선, 일일 수익률은 전일 대비."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market.providers.base import DailyPriceBar


def bars_to_silver_rows(
    bars: list[DailyPriceBar],
    *,
    cik: str | None,
    source_name: str,
) -> list[dict[str, Any]]:
    """같은 symbol 바만 전달. trade_date 오름차순 정렬 가정(호출부에서 정렬)."""
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    prev_adj: float | None = None
    for b in bars:
        close_v = float(b.close) if b.close is not None else None
        adj_v = float(b.adjusted_close) if b.adjusted_close is not None else close_v
        if adj_v is None and close_v is None:
            continue
        basis = adj_v if b.adjusted_close is not None else close_v
        assert basis is not None
        daily_return: float | None = None
        if prev_adj is not None and prev_adj != 0:
            daily_return = basis / prev_adj - 1.0
        prev_adj = basis
        notes: dict[str, Any] = {
            "source": source_name,
            "used_adjusted_close": b.adjusted_close is not None,
        }
        rows.append(
            {
                "symbol": b.symbol.upper().strip(),
                "cik": cik,
                "trade_date": b.trade_date.isoformat(),
                "close": float(close_v) if close_v is not None else float(basis),
                "adjusted_close": float(adj_v) if b.adjusted_close is not None else None,
                "volume": float(b.volume) if b.volume is not None else None,
                "daily_return": daily_return,
                "is_trading_day": True,
                "normalization_notes_json": notes,
                "updated_at": now,
                "created_at": now,
            }
        )
    return rows
