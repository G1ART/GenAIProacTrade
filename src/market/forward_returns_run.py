"""factor panel / 스냅샷 기준 선행 수익률(next_month, next_quarter)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from db.client import get_supabase_client
from db.records import (
    fetch_factor_panels_all,
    fetch_quarter_snapshot_by_accession,
    fetch_risk_free_range,
    fetch_silver_prices_for_symbol_range,
    fetch_ticker_for_cik,
    upsert_forward_return_row,
    ingest_run_create_started,
    ingest_run_finalize,
)
from market.forward_math import (
    excess_return_simple,
    forward_return_over_trading_days,
    sorted_price_series,
)
from market.risk_free_fred import SOURCE_NAME
from market.run_types import FORWARD_RETURN_BUILD
from market.signal_date import signal_available_date_from_snapshot

logger = logging.getLogger(__name__)

H_NEXT_MONTH = "next_month"
H_NEXT_QUARTER = "next_quarter"
TRADING_DAYS_1M = 21
TRADING_DAYS_1Q = 63


def run_forward_returns_build_from_rows(
    settings: Any,
    *,
    panels: list[dict[str, Any]],
    metadata_json: dict[str, Any] | None = None,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    """issuer_quarter_factor_panels 행만 대상으로 선행 수익률 갱신(Phase 25 타깃 백필)."""
    client = get_supabase_client(settings)
    meta = dict(metadata_json or {})
    meta["n_input_panels"] = len(panels)
    run_id = ingest_run_create_started(
        client,
        run_type=FORWARD_RETURN_BUILD,
        target_count=len(panels),
        metadata_json=meta,
    )
    return _forward_returns_build_loop(
        client, run_id, panels, price_lookahead_days=price_lookahead_days
    )


def run_forward_returns_build(
    settings: Any,
    *,
    limit_panels: int = 2000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    panels = fetch_factor_panels_all(client, limit=limit_panels)
    run_id = ingest_run_create_started(
        client,
        run_type=FORWARD_RETURN_BUILD,
        target_count=len(panels),
        metadata_json={"limit_panels": limit_panels},
    )
    return _forward_returns_build_loop(
        client, run_id, panels, price_lookahead_days=price_lookahead_days
    )


def _forward_returns_build_loop(
    client: Any,
    run_id: str,
    panels: list[dict[str, Any]],
    *,
    price_lookahead_days: int,
) -> dict[str, Any]:
    ok = 0
    fail = 0
    errors: list[dict[str, Any]] = []
    for panel in panels:
        cik = str(panel["cik"])
        acc = str(panel["accession_no"])
        sym_db = fetch_ticker_for_cik(client, cik=cik)
        if not sym_db:
            fail += 1
            errors.append({"cik": cik, "accession_no": acc, "error": "no_ticker_in_issuer_master"})
            continue
        snap = fetch_quarter_snapshot_by_accession(client, cik=cik, accession_no=acc)
        if not snap:
            fail += 1
            errors.append({"cik": cik, "accession_no": acc, "error": "no_quarter_snapshot"})
            continue
        try:
            sig = signal_available_date_from_snapshot(snap)
        except (ValueError, TypeError) as e:
            fail += 1
            errors.append({"cik": cik, "accession_no": acc, "error": f"signal_date:{e}"})
            continue
        sig_s = sig.isoformat()
        start_fetch = (sig - timedelta(days=5)).isoformat()
        end_fetch = (sig + timedelta(days=price_lookahead_days)).isoformat()
        sprices = fetch_silver_prices_for_symbol_range(
            client, symbol=sym_db, start_date=start_fetch, end_date=end_fetch
        )
        series = sorted_price_series(sprices)
        rf_rows = fetch_risk_free_range(
            client,
            start_date=start_fetch,
            end_date=end_fetch,
            source_name=SOURCE_NAME,
        )
        rates = [float(r["annualized_rate"]) for r in rf_rows if r.get("annualized_rate") is not None]
        for htype, off in ((H_NEXT_MONTH, TRADING_DAYS_1M), (H_NEXT_QUARTER, TRADING_DAYS_1Q)):
            fr = forward_return_over_trading_days(series, sig, off)
            if not fr:
                fail += 1
                errors.append(
                    {
                        "symbol": sym_db,
                        "signal_date": sig_s,
                        "horizon": htype,
                        "error": "insufficient_price_history",
                    }
                )
                continue
            d0, d1, raw, basis = fr
            n_sessions = basis.get("trading_sessions_spanned") or off
            ex, ex_meta = excess_return_simple(raw, num_trading_periods=int(n_sessions), annualized_rates_pct=rates)
            basis_full = {
                **basis,
                "horizon_type": htype,
                "signal_date": sig_s,
                "excess_meta": ex_meta,
            }
            upsert_forward_return_row(
                client,
                {
                    "symbol": sym_db.upper(),
                    "cik": cik,
                    "signal_date": sig_s,
                    "horizon_type": htype,
                    "start_trade_date": d0.isoformat(),
                    "end_trade_date": d1.isoformat(),
                    "raw_forward_return": raw,
                    "excess_forward_return": ex,
                    "return_basis_json": basis_full,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            ok += 1
    ingest_run_finalize(
        client,
        run_id=run_id,
        status="completed",
        success_count=ok,
        failure_count=fail,
        error_json={"errors": errors[:200]} if errors else None,
    )
    return {
        "status": "completed",
        "panels_seen": len(panels),
        "success_operations": ok,
        "failures": fail,
        "error_sample": errors[:20],
    }
