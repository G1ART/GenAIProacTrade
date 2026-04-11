"""전파 감사에서 `missing_market_prices_daily_window` 로만 분류된 (symbol, signal) 에 한해 일봉 수집."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from db import records as dbrec
from market.price_ingest import run_market_prices_ingest_for_symbols


def run_bounded_price_ingest_for_propagation_missing_windows(
    settings: Any,
    client: Any,
    *,
    propagation_gap_report: dict[str, Any],
    price_lookahead_days: int = 400,
    extend_calendar_buffer_days: int = 30,
) -> dict[str, Any]:
    to_fetch: list[tuple[str, date, date]] = []
    for row in propagation_gap_report.get("rows") or []:
        pg = row.get("price_gap") or {}
        if pg.get("classification") != "missing_market_prices_daily_window":
            continue
        sym = str(row.get("symbol") or "").upper().strip()
        sig_s = str(row.get("signal_available_date") or "")[:10]
        if not sym or len(sig_s) < 10:
            continue
        sig = date.fromisoformat(sig_s)
        start_d = sig - timedelta(days=5)
        end_d = min(
            date.today(),
            sig + timedelta(days=price_lookahead_days + extend_calendar_buffer_days),
        )
        to_fetch.append((sym, start_d, end_d))

    if not to_fetch:
        return {
            "ok": True,
            "repair": "bounded_price_ingest_propagation_missing_window",
            "ingest_attempted": False,
            "price_coverage_repaired_now_count": 0,
            "note": "no_missing_market_prices_daily_window_in_propagation_rows",
        }

    by_sym: dict[str, tuple[date, date]] = {}
    for sym, sd, ed in to_fetch:
        if sym not in by_sym:
            by_sym[sym] = (sd, ed)
        else:
            o0, o1 = by_sym[sym]
            by_sym[sym] = (min(o0, sd), max(o1, ed))

    symbols = sorted(by_sym.keys())
    start_date = min(a[0] for a in by_sym.values())
    end_date = max(a[1] for a in by_sym.values())
    ing = run_market_prices_ingest_for_symbols(
        settings,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        metadata_json={"phase34": "propagation_missing_window_only"},
    )

    recovered: list[dict[str, Any]] = []
    if ing.get("status") == "completed":
        for sym in symbols:
            sd, ed = by_sym[sym]
            after = dbrec.fetch_silver_prices_for_symbol_range(
                client,
                symbol=sym,
                start_date=sd.isoformat(),
                end_date=ed.isoformat(),
            )
            if len(after) > 0:
                recovered.append({"symbol": sym, "silver_rows": len(after)})

    return {
        "ok": True,
        "repair": "bounded_price_ingest_propagation_missing_window",
        "ingest": ing,
        "ingest_attempted": True,
        "symbols": symbols,
        "price_coverage_repaired_now_count": len(recovered),
        "recovered": recovered,
    }
