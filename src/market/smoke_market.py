"""smoke-market: DB 테이블 + (선택) 스텁 프로바이더 결과 형태."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from db.client import get_supabase_client
from db.records import smoke_market_tables
from market.providers.stub_provider import StubMarketProvider


def run_smoke_market(settings: Any) -> dict[str, Any]:
    client = get_supabase_client(settings)
    smoke_market_tables(client)
    p = StubMarketProvider()
    end = date.today()
    start = end - timedelta(days=10)
    bars = p.fetch_daily_prices(["ZZZ"], start, end)
    meta = p.fetch_market_metadata(["ZZZ"])
    cons = p.fetch_index_constituents("sp500_current")
    sample_keys = (
        ["symbol", "trade_date", "close", "adjusted_close"]
        if bars
        else []
    )
    return {
        "db": "ok",
        "stub_bar_sample_keys": sample_keys,
        "stub_meta_count": len(meta),
        "stub_constituents": len(cons),
    }


def run_smoke_validation(settings: Any) -> dict[str, Any]:
    from db.records import smoke_validation_panel_table

    client = get_supabase_client(settings)
    smoke_validation_panel_table(client)
    return {"db_validation_panel": "ok"}
