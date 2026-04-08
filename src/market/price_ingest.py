"""유니버스 심볼 일봉 수집 → raw + silver."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from db.client import get_supabase_client
from db.records import (
    fetch_cik_map_for_tickers,
    fetch_market_metadata_latest_rows_for_symbols,
    fetch_max_as_of_universe,
    fetch_symbols_universe_as_of,
    upsert_market_metadata_latest,
    upsert_raw_market_prices_batch,
    upsert_silver_market_prices_batch,
    ingest_run_create_started,
    ingest_run_finalize,
)
from market.price_normalize import bars_to_silver_rows
from market.provider_factory import get_market_provider
from market.providers.base import MarketMetadataRow
from market.run_types import (
    MARKET_METADATA_REFRESH,
    MARKET_PRICES_INGEST,
    UNIVERSE_PROXY_CANDIDATES,
    UNIVERSE_SP500_CURRENT,
)

logger = logging.getLogger(__name__)


def _metadata_row_current_enough(
    existing: dict[str, Any],
    m: MarketMetadataRow,
) -> bool:
    """동일 as_of·유사 avg_daily_volume 이면 upsert 생략."""
    ex_asof = str(existing.get("as_of_date") or "")[:10]
    m_asof = m.as_of_date.isoformat()
    if ex_asof > m_asof:
        return True
    if ex_asof < m_asof:
        return False
    ex_v = existing.get("avg_daily_volume")
    mv = m.avg_daily_volume
    if ex_v is not None and mv is not None:
        try:
            return abs(float(ex_v) - float(mv)) < 1.0
        except (TypeError, ValueError):
            return False
    return ex_v is None and mv is None


def _symbol_still_missing_avg_meta(row: dict[str, Any] | None) -> bool:
    if not row:
        return True
    return row.get("avg_daily_volume") is None


def run_market_prices_ingest(
    settings: Any,
    *,
    universe_name: str,
    start_date: date | None = None,
    end_date: date | None = None,
    lookback_days: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    provider = get_market_provider()
    as_of = fetch_max_as_of_universe(client, universe_name=universe_name)
    if not as_of:
        if universe_name == UNIVERSE_PROXY_CANDIDATES:
            hint = (
                "먼저 `python3 src/main.py build-candidate-universe` 실행 "
                f"(전제: {UNIVERSE_SP500_CURRENT} 멤버십이 이미 있어야 시드에서 후보를 뺍니다)."
            )
        elif universe_name == UNIVERSE_SP500_CURRENT:
            hint = "`python3 src/main.py refresh-universe --universe sp500_current` 실행."
        else:
            hint = "해당 유니버스를 채우는 CLI를 먼저 실행하세요."
        return {
            "status": "failed",
            "error": f"유니버스 {universe_name} 멤버십이 없습니다. {hint}",
        }
    symbols = fetch_symbols_universe_as_of(
        client, universe_name=universe_name, as_of_date=as_of
    )
    if not symbols:
        return {"status": "failed", "error": "심볼 목록이 비어 있습니다."}
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=lookback_days))
    run_id = ingest_run_create_started(
        client,
        run_type=MARKET_PRICES_INGEST,
        target_count=len(symbols),
        metadata_json={
            "universe_name": universe_name,
            "universe_as_of": as_of,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "provider": provider.name,
        },
    )
    success = 0
    failures = 0
    errors: list[dict[str, Any]] = []
    now_ing = datetime.now(timezone.utc).isoformat()
    try:
        bars = provider.fetch_daily_prices(symbols, start, end)
        by_sym: dict[str, list] = {}
        for b in bars:
            by_sym.setdefault(b.symbol.upper(), []).append(b)
        cik_map = fetch_cik_map_for_tickers(client, symbols)
        raw_rows: list[dict[str, Any]] = []
        silver_rows: list[dict[str, Any]] = []
        for sym, blist in by_sym.items():
            blist.sort(key=lambda x: x.trade_date)
            cik = cik_map.get(sym.upper())
            for b in blist:
                raw_rows.append(
                    {
                        "symbol": sym,
                        "trade_date": b.trade_date.isoformat(),
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "adjusted_close": b.adjusted_close,
                        "volume": b.volume,
                        "source_name": provider.name,
                        "source_payload_json": dict(b.raw_payload),
                        "ingested_at": now_ing,
                    }
                )
            silver_rows.extend(
                bars_to_silver_rows(blist, cik=cik, source_name=provider.name)
            )
            success += 1
        upsert_raw_market_prices_batch(client, raw_rows)
        upsert_silver_market_prices_batch(client, silver_rows)
        for s in symbols:
            if s not in by_sym:
                failures += 1
                errors.append({"symbol": s, "error": "no_bars_from_provider"})
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            success_count=success,
            failure_count=failures,
            error_json={"errors": errors} if errors else None,
        )
        return {
            "status": "completed",
            "universe_name": universe_name,
            "symbols_requested": len(symbols),
            "symbols_with_data": success,
            "missing": failures,
            "raw_rows": len(raw_rows),
            "silver_rows": len(silver_rows),
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("market_prices_ingest")
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="failed",
            success_count=success,
            failure_count=len(symbols),
            error_json={"error": str(ex)},
        )
        return {"status": "failed", "error": str(ex)}


def run_market_metadata_refresh(settings: Any, *, universe_name: str) -> dict[str, Any]:
    """프로바이더가 메타를 주지 않으면 no-op + 감사 로그만 남김."""
    client = get_supabase_client(settings)
    provider = get_market_provider()
    as_of = fetch_max_as_of_universe(client, universe_name=universe_name)
    if not as_of:
        if universe_name == UNIVERSE_PROXY_CANDIDATES:
            hint = "먼저 build-candidate-universe."
        elif universe_name == UNIVERSE_SP500_CURRENT:
            hint = "먼저 refresh-universe --universe sp500_current."
        else:
            hint = "유니버스 멤버십을 먼저 적재하세요."
        return {"status": "failed", "error": f"유니버스 {universe_name}: {hint}"}
    symbols = fetch_symbols_universe_as_of(
        client, universe_name=universe_name, as_of_date=as_of
    )
    sym_list = sorted({str(s).upper().strip() for s in symbols if s})
    run_id = ingest_run_create_started(
        client,
        run_type=MARKET_METADATA_REFRESH,
        target_count=len(sym_list),
        metadata_json={"universe_name": universe_name, "provider": provider.name},
    )
    pre_meta = fetch_market_metadata_latest_rows_for_symbols(client, sym_list)
    meta = provider.fetch_market_metadata(sym_list)
    provider_rows_returned = len(meta)
    rows_attempted_for_upsert = 0
    rows_already_current = 0
    rows_upserted = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    if sym_list and provider_rows_returned == 0:
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            success_count=0,
            failure_count=0,
            error_json={
                "blocked_reason": "provider_returned_zero_metadata_rows",
                "provider": provider.name,
            },
        )
        return {
            "status": "blocked",
            "blocked_reason": "provider_returned_zero_metadata_rows",
            "symbols_requested": len(sym_list),
            "provider_rows_returned": 0,
            "rows_upserted": 0,
            "rows_attempted_for_upsert": 0,
            "rows_already_current": 0,
            "rows_missing_after_requery": len(sym_list),
            "provider": provider.name,
        }
    for m in meta:
        rows_attempted_for_upsert += 1
        su = m.symbol.upper()
        ex = pre_meta.get(su)
        if ex and _metadata_row_current_enough(ex, m):
            rows_already_current += 1
            continue
        upsert_market_metadata_latest(
            client,
            {
                "symbol": su,
                "cik": None,
                "as_of_date": m.as_of_date.isoformat(),
                "market_cap": m.market_cap,
                "shares_outstanding": m.shares_outstanding,
                "avg_daily_volume": m.avg_daily_volume,
                "exchange": m.exchange,
                "sector": m.sector,
                "industry": m.industry,
                "source_name": provider.name,
                "metadata_json": dict(m.raw_payload),
                "created_at": now_iso,
            },
        )
        rows_upserted += 1
    post_meta = fetch_market_metadata_latest_rows_for_symbols(client, sym_list)
    rows_missing_after_requery = sum(
        1 for s in sym_list if _symbol_still_missing_avg_meta(post_meta.get(s))
    )
    ingest_run_finalize(
        client,
        run_id=run_id,
        status="completed",
        success_count=rows_upserted + rows_already_current,
        failure_count=0,
        error_json=None,
    )
    return {
        "status": "completed",
        "symbols_requested": len(sym_list),
        "provider_rows_returned": provider_rows_returned,
        "rows_attempted_for_upsert": rows_attempted_for_upsert,
        "rows_already_current": rows_already_current,
        "rows_upserted": rows_upserted,
        "rows_missing_after_requery": rows_missing_after_requery,
        "provider": provider.name,
    }


def run_market_metadata_hydration_for_symbols(
    settings: Any,
    *,
    universe_name: str,
    symbols: list[str],
) -> dict[str, Any]:
    """Phase 27: 유니버스 맥락 검증 후 지정 심볼만 메타데이터 갱신(전 유니버스 스캔 아님)."""
    client = get_supabase_client(settings)
    provider = get_market_provider()
    as_of = fetch_max_as_of_universe(client, universe_name=universe_name)
    if not as_of:
        return {
            "status": "failed",
            "error": f"유니버스 {universe_name}: 멤버십 as_of 없음",
        }
    allowed = set(
        fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of
        )
    )
    want = sorted(
        {
            str(s).upper().strip()
            for s in symbols
            if s and str(s).strip() and str(s).upper().strip() in allowed
        }
    )
    if not want:
        return {
            "status": "skipped",
            "reason": "no_symbols_in_universe_or_empty_input",
            "rows_upserted": 0,
        }
    run_id = ingest_run_create_started(
        client,
        run_type=MARKET_METADATA_REFRESH,
        target_count=len(want),
        metadata_json={
            "universe_name": universe_name,
            "provider": provider.name,
            "phase27": "hydration_subset",
            "symbol_count": len(want),
        },
    )
    pre_meta = fetch_market_metadata_latest_rows_for_symbols(client, want)
    meta = provider.fetch_market_metadata(want)
    provider_rows_returned = len(meta)
    rows_attempted_for_upsert = 0
    rows_already_current = 0
    rows_upserted = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    if want and provider_rows_returned == 0:
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            success_count=0,
            failure_count=0,
            error_json={
                "blocked_reason": "provider_returned_zero_metadata_rows",
                "provider": provider.name,
            },
        )
        return {
            "status": "blocked",
            "blocked_reason": "provider_returned_zero_metadata_rows",
            "symbols_requested": len(want),
            "provider_rows_returned": 0,
            "rows_upserted": 0,
            "rows_attempted_for_upsert": 0,
            "rows_already_current": 0,
            "rows_missing_after_requery": len(want),
            "provider": provider.name,
        }
    for m in meta:
        rows_attempted_for_upsert += 1
        su = m.symbol.upper()
        ex = pre_meta.get(su)
        if ex and _metadata_row_current_enough(ex, m):
            rows_already_current += 1
            continue
        upsert_market_metadata_latest(
            client,
            {
                "symbol": su,
                "cik": None,
                "as_of_date": m.as_of_date.isoformat(),
                "market_cap": m.market_cap,
                "shares_outstanding": m.shares_outstanding,
                "avg_daily_volume": m.avg_daily_volume,
                "exchange": m.exchange,
                "sector": m.sector,
                "industry": m.industry,
                "source_name": provider.name,
                "metadata_json": dict(m.raw_payload),
                "created_at": now_iso,
            },
        )
        rows_upserted += 1
    post_meta = fetch_market_metadata_latest_rows_for_symbols(client, want)
    rows_missing_after_requery = sum(
        1 for s in want if _symbol_still_missing_avg_meta(post_meta.get(s))
    )
    ingest_run_finalize(
        client,
        run_id=run_id,
        status="completed",
        success_count=rows_upserted + rows_already_current,
        failure_count=0,
        error_json=None,
    )
    return {
        "status": "completed",
        "symbols_requested": len(want),
        "provider_rows_returned": provider_rows_returned,
        "rows_attempted_for_upsert": rows_attempted_for_upsert,
        "rows_already_current": rows_already_current,
        "rows_upserted": rows_upserted,
        "rows_missing_after_requery": rows_missing_after_requery,
        "provider": provider.name,
    }
