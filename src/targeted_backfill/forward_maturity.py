"""Phase 27 C: forward 1Q 갭의 성숙도(달력 프록시) vs 진짜 결손."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from db import records as dbrec
from market.forward_math import forward_return_over_trading_days, sorted_price_series
from market.forward_returns_run import TRADING_DAYS_1Q
from research_validation.metrics import norm_signal_date
from substrate_closure.diagnose import report_forward_return_gaps
from targeted_backfill.constants import CALENDAR_DAYS_1Q_MATURITY_PROXY

_BUCKET_IMMATURE = "not_yet_matured_for_1q_horizon"
_BUCKET_MATURED_MISSING = "matured_but_forward_row_missing"
_BUCKET_PRICE = "price_history_insufficient_after_signal"
_BUCKET_NO_LINK = "symbol_price_link_missing"


def _maturity_cutoff_date(signal_iso: str) -> date:
    return date.fromisoformat(signal_iso[:10]) + timedelta(days=CALENDAR_DAYS_1Q_MATURITY_PROXY)


def classify_forward_gap_maturity_row(
    *,
    symbol: str,
    signal_date_raw: Any,
    eval_date: date,
    client: Any,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    sig_s = norm_signal_date(signal_date_raw)
    if not sig_s:
        return {
            "symbol": sym,
            "signal_date": None,
            "maturity_cutoff_date": None,
            "bucket": _BUCKET_MATURED_MISSING,
            "note": "missing_signal_date",
        }
    cutoff = _maturity_cutoff_date(sig_s)
    if eval_date < cutoff:
        return {
            "symbol": sym,
            "signal_date": sig_s,
            "maturity_cutoff_date": cutoff.isoformat(),
            "bucket": _BUCKET_IMMATURE,
            "calendar_days_proxy": CALENDAR_DAYS_1Q_MATURITY_PROXY,
        }

    start_fetch = (date.fromisoformat(sig_s[:10]) - timedelta(days=5)).isoformat()
    end_fetch = (date.fromisoformat(sig_s[:10]) + timedelta(days=price_lookahead_days)).isoformat()
    sprices = dbrec.fetch_silver_prices_for_symbol_range(
        client, symbol=sym, start_date=start_fetch, end_date=end_fetch
    )
    if not sprices:
        return {
            "symbol": sym,
            "signal_date": sig_s,
            "maturity_cutoff_date": cutoff.isoformat(),
            "bucket": _BUCKET_NO_LINK,
        }
    series = sorted_price_series(sprices)
    fr = forward_return_over_trading_days(
        series, date.fromisoformat(sig_s[:10]), TRADING_DAYS_1Q
    )
    if fr is None:
        return {
            "symbol": sym,
            "signal_date": sig_s,
            "maturity_cutoff_date": cutoff.isoformat(),
            "bucket": _BUCKET_PRICE,
        }
    return {
        "symbol": sym,
        "signal_date": sig_s,
        "maturity_cutoff_date": cutoff.isoformat(),
        "bucket": _BUCKET_MATURED_MISSING,
    }


def report_forward_gap_maturity(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    eval_date: date | None = None,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    ed = eval_date or date.today()
    base = report_forward_return_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    raw_rows = list((base.get("row_reason_buckets") or {}).get("no_forward_row_next_quarter", []))

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        out = classify_forward_gap_maturity_row(
            symbol=str(row.get("symbol") or ""),
            signal_date_raw=row.get("signal_date"),
            eval_date=ed,
            client=client,
            price_lookahead_days=price_lookahead_days,
        )
        b = str(out.get("bucket") or "")
        merged = {**row, **out}
        buckets[b].append(merged)

    all_classified = [x for xs in buckets.values() for x in xs]
    true_repairable = sum(
        1
        for r in all_classified
        if r.get("bucket")
        in (_BUCKET_MATURED_MISSING, _BUCKET_PRICE, _BUCKET_NO_LINK)
    )
    not_matured = len(buckets.get(_BUCKET_IMMATURE, []))

    return {
        "ok": True,
        "universe_name": universe_name,
        "eval_date": ed.isoformat(),
        "calendar_days_1q_proxy": CALENDAR_DAYS_1Q_MATURITY_PROXY,
        "raw_unresolved_forward_row_count": len(raw_rows),
        "true_repairable_forward_gap_count": true_repairable,
        "not_yet_matured_count": not_matured,
        "maturity_bucket_counts": {k: len(v) for k, v in buckets.items()},
        "maturity_buckets_sample": {k: v[:50] for k, v in buckets.items()},
        "maturity_all_rows": all_classified,
        "forward_gap_base": {
            "metrics": base.get("metrics"),
            "row_reason_counts": base.get("row_reason_counts"),
        },
    }


def export_forward_gap_maturity_buckets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    eval_date: date | None = None,
    price_lookahead_days: int = 400,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    import csv
    import json
    from pathlib import Path

    rep = report_forward_gap_maturity(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        eval_date=eval_date,
        price_lookahead_days=price_lookahead_days,
    )
    rows = list(rep.get("maturity_all_rows") or [])

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and rows:
        keys = sorted({k for row in rows for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    elif fmt == "csv":
        p.write_text(
            "symbol,signal_date,maturity_cutoff_date,bucket,cik,accession_no\n",
            encoding="utf-8",
        )
    else:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "path": str(p), "count": len(rows), "format": fmt}
