"""Phase 32 `insufficient_price_history` 대상 가격 커버리지 분류·상한 백필."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from db import records as dbrec
from market.forward_math import forward_return_over_trading_days, sorted_price_series
from market.forward_returns_run import TRADING_DAYS_1Q
from market.price_ingest import run_market_prices_ingest_for_symbols
from phase33.phase32_bundle_io import load_phase32_bundle, phase32_insufficient_price_errors_next_q


def _sessions_from_signal(
    series: list[tuple[date, float, str]], signal_d: date
) -> int | None:
    start_i = None
    for i, (d, _, _) in enumerate(series):
        if d >= signal_d:
            start_i = i
            break
    if start_i is None:
        return None
    return len(series) - start_i


def classify_price_gap_for_forward_row(
    client: Any,
    *,
    symbol: str,
    signal_date_s: str,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    sym = symbol.upper().strip()
    sig = date.fromisoformat(signal_date_s[:10])
    today = date.today()
    end_cal = sig + timedelta(days=price_lookahead_days)
    start_fetch = (sig - timedelta(days=5)).isoformat()
    end_fetch = end_cal.isoformat()
    sprices = dbrec.fetch_silver_prices_for_symbol_range(
        client, symbol=sym, start_date=start_fetch, end_date=end_fetch
    )
    series = sorted_price_series(sprices)
    n_after = _sessions_from_signal(series, sig)

    if not sym:
        bucket = "symbol_registry_or_time_alignment_issue"
        detail = "empty_symbol"
    elif len(series) == 0:
        bucket = "missing_market_prices_daily_window"
        detail = "no_silver_rows_in_fetch_window"
    else:
        fr = forward_return_over_trading_days(series, sig, TRADING_DAYS_1Q)
        if fr:
            bucket = "would_compute_now"
            detail = "forward_math_ok"
        elif n_after is None:
            bucket = "symbol_registry_or_time_alignment_issue"
            detail = "no_session_on_or_after_signal_in_series"
        elif end_cal > today and n_after <= TRADING_DAYS_1Q + 1:
            bucket = "lookahead_window_not_matured"
            detail = (
                f"calendar_window_reaches_past_today_sessions_after_signal={n_after}"
            )
        else:
            bucket = "insufficient_price_history_recent_signal"
            detail = (
                f"sessions_after_signal={n_after}_need_more_than_{TRADING_DAYS_1Q}"
            )

    return {
        "symbol": sym,
        "signal_date": signal_date_s[:10],
        "classification": bucket,
        "detail": detail,
        "silver_row_count_in_window": len(sprices),
        "sessions_on_or_after_signal": n_after,
    }


def report_price_coverage_gaps_for_forward(
    client: Any,
    *,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("bundle or path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)
    errs = phase32_insufficient_price_errors_next_q(phase32_bundle)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for e in errs:
        sym = str(e.get("symbol") or "")
        sig = str(e.get("signal_date") or "")
        if not sym or not sig:
            continue
        c = classify_price_gap_for_forward_row(
            client,
            symbol=sym,
            signal_date_s=sig,
            price_lookahead_days=price_lookahead_days,
        )
        rows.append({**e, "price_gap": c})
        k = c["classification"]
        counts[k] = counts.get(k, 0) + 1
    return {
        "ok": True,
        "source_error_row_count": len(errs),
        "classified_rows": rows,
        "classification_counts": counts,
    }


def run_price_coverage_backfill_for_forward(
    settings: Any,
    client: Any,
    *,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    price_lookahead_days: int = 400,
    extend_calendar_buffer_days: int = 30,
) -> dict[str, Any]:
    """`missing_market_prices_daily_window` 에 한해 프로바이더 일봉 수집 시도."""
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("bundle or path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)
    rep = report_price_coverage_gaps_for_forward(
        client,
        phase32_bundle=phase32_bundle,
        price_lookahead_days=price_lookahead_days,
    )
    to_fetch: list[tuple[str, date, date]] = []
    for row in rep.get("classified_rows") or []:
        pg = row.get("price_gap") or {}
        if pg.get("classification") != "missing_market_prices_daily_window":
            continue
        sym = str(row.get("symbol") or "").upper().strip()
        sig = date.fromisoformat(str(row.get("signal_date") or "")[:10])
        start_d = sig - timedelta(days=5)
        end_d = min(
            date.today(),
            sig + timedelta(days=price_lookahead_days + extend_calendar_buffer_days),
        )
        if sym:
            to_fetch.append((sym, start_d, end_d))

    recovered: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    if not to_fetch:
        return {
            "ok": True,
            "repair": "price_coverage_backfill",
            "report": rep,
            "ingest_attempted": False,
            "price_coverage_repaired_now_count": 0,
            "price_coverage_deferred_count": 0,
            "price_coverage_blocked_count": 0,
            "note": "no_missing_market_prices_daily_window_targets",
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
        metadata_json={"phase33": "price_coverage_backfill_for_forward"},
    )

    for sym in symbols:
        sd, ed = by_sym[sym]
        if ing.get("status") != "completed":
            blocked.append({"symbol": sym, "reason": "ingest_not_completed", "ingest": ing})
            continue
        after = dbrec.fetch_silver_prices_for_symbol_range(
            client,
            symbol=sym,
            start_date=sd.isoformat(),
            end_date=ed.isoformat(),
        )
        if len(after) > 0:
            recovered.append({"symbol": sym, "silver_rows": len(after)})
        else:
            deferred.append({"symbol": sym, "reason": "still_no_silver_after_ingest"})

    return {
        "ok": True,
        "repair": "price_coverage_backfill",
        "report": rep,
        "ingest": ing,
        "ingest_attempted": True,
        "price_coverage_repaired_now_count": len(recovered),
        "price_coverage_deferred_count": len(deferred),
        "price_coverage_blocked_count": len(blocked),
        "recovered": recovered,
        "deferred": deferred,
        "blocked": blocked,
    }


def export_price_coverage_report(rep: dict[str, Any], *, out_json: str) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())
