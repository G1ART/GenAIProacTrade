"""Phase 27 B: 조인된 recipe 행의 market_metadata 누락 원인."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from db import records as dbrec
from market.forward_math import forward_return_over_trading_days, sorted_price_series
from market.forward_returns_run import TRADING_DAYS_1Q
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.metrics import norm_signal_date
from thin_input_root_cause.decompose import _joined_row_driver_bucket

_BUCKET_NO_META = "missing_market_metadata_latest"
_BUCKET_NO_REGISTRY = "missing_market_symbol_registry_link"
_BUCKET_PRICE = "missing_price_history_window"
_BUCKET_ASOF = "metadata_asof_misaligned"
_BUCKET_OTHER = "metadata_gap_other"


def _classify_joined_metadata_row(
    row: dict[str, Any],
    *,
    registry_by_sym: dict[str, dict[str, Any]],
    meta_by_sym: dict[str, dict[str, Any]],
    client: Any,
    price_lookahead_days: int = 400,
) -> str:
    sym = str(row.get("symbol") or "").upper().strip()
    sig = norm_signal_date(row.get("signal_available_date"))

    if sym not in registry_by_sym:
        return _BUCKET_NO_REGISTRY

    fm = meta_by_sym.get(sym)
    if not fm:
        return _BUCKET_NO_META

    asof_raw = fm.get("as_of_date")
    asof_s = str(asof_raw)[:10] if asof_raw else ""
    if sig and asof_s and asof_s < sig:
        return _BUCKET_ASOF

    if not sig:
        return _BUCKET_OTHER

    start_fetch = (date.fromisoformat(sig) - timedelta(days=5)).isoformat()
    end_fetch = (date.fromisoformat(sig) + timedelta(days=price_lookahead_days)).isoformat()
    sprices = dbrec.fetch_silver_prices_for_symbol_range(
        client, symbol=sym, start_date=start_fetch, end_date=end_fetch
    )
    if not sprices:
        return _BUCKET_PRICE
    series = sorted_price_series(sprices)
    fr = forward_return_over_trading_days(
        series, date.fromisoformat(str(sig)[:10]), TRADING_DAYS_1Q
    )
    if fr is None:
        return _BUCKET_PRICE

    return _BUCKET_OTHER


def report_market_metadata_gap_drivers(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    joined: list[dict[str, Any]] = []
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        joined_panels_out=joined,
    )
    meta_flagged = [r for r in joined if _joined_row_driver_bucket(r) == "joined_but_market_metadata_flagged"]
    syms = sorted({str(r.get("symbol") or "").upper().strip() for r in meta_flagged if r.get("symbol")})
    registry_by_sym = dbrec.fetch_market_symbol_registry_rows_for_symbols(client, syms)
    meta_by_sym = dbrec.fetch_market_metadata_latest_rows_for_symbols(client, syms)

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in meta_flagged:
        b = _classify_joined_metadata_row(
            row,
            registry_by_sym=registry_by_sym,
            meta_by_sym=meta_by_sym,
            client=client,
            price_lookahead_days=price_lookahead_days,
        )
        buckets[b].append(
            {
                "symbol": row.get("symbol"),
                "cik": row.get("cik"),
                "signal_available_date": row.get("signal_available_date"),
                "driver_bucket": b,
            }
        )

    all_rows = [x for xs in buckets.values() for x in xs]
    return {
        "ok": True,
        "universe_name": universe_name,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "joined_row_count": len(joined),
        "joined_market_metadata_flagged_count": len(meta_flagged),
        "metadata_gap_bucket_counts": {k: len(v) for k, v in buckets.items()},
        "metadata_gap_buckets_sample": {k: v[:40] for k, v in buckets.items()},
        "metadata_gap_all_rows": all_rows,
    }


def run_market_metadata_hydration_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    from db.client import get_supabase_client
    from market.price_ingest import run_market_metadata_hydration_for_symbols

    c = get_supabase_client(settings)
    before = report_market_metadata_gap_drivers(
        c,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    meta_flagged_before = int(before.get("joined_market_metadata_flagged_count") or 0)

    syms = {
        str(r.get("symbol") or "").upper().strip()
        for r in (before.get("metadata_gap_all_rows") or [])
        if r.get("symbol")
    }
    hydrate_targets = sorted(syms)
    build_out = run_market_metadata_hydration_for_symbols(
        settings,
        universe_name=universe_name,
        symbols=hydrate_targets,
    )

    after = report_market_metadata_gap_drivers(
        c,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    meta_flagged_after = int(after.get("joined_market_metadata_flagged_count") or 0)

    return {
        "ok": True,
        "repair": "market_metadata_hydration",
        "universe_name": universe_name,
        "before": {"joined_market_metadata_flagged_count": meta_flagged_before},
        "after": {"joined_market_metadata_flagged_count": meta_flagged_after},
        "hydration": build_out,
        "symbols_touched": hydrate_targets,
    }


def export_market_metadata_gap_rows(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    import csv
    import json
    from pathlib import Path

    rep = report_market_metadata_gap_drivers(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    rows = list(rep.get("metadata_gap_all_rows") or [])
    for r in rows:
        r.setdefault("gap_bucket", r.get("driver_bucket"))

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and rows:
        keys = sorted({k for row in rows for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    elif fmt == "csv":
        p.write_text("symbol,cik,signal_available_date,driver_bucket,gap_bucket\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "path": str(p),
        "count": len(rows),
        "format": fmt,
    }
