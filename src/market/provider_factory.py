"""MARKET_DATA_PROVIDER 환경변수로 구현체 선택."""

from __future__ import annotations

import os

from market.providers.base import MarketDataProvider
from market.providers.stub_provider import StubMarketProvider
from market.providers.yahoo_chart_provider import YahooChartMarketProvider


def get_market_provider() -> MarketDataProvider:
    name = (os.getenv("MARKET_DATA_PROVIDER") or "yahoo_chart").strip().lower()
    if name in ("stub", "test", "mock"):
        return StubMarketProvider()
    if name in ("yahoo", "yahoo_chart", "default"):
        return YahooChartMarketProvider()
    raise RuntimeError(
        f"지원하지 않는 MARKET_DATA_PROVIDER={name!r}. "
        "사용 가능: yahoo_chart, stub"
    )
