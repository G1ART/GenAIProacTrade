"""결정적 스텁 프로바이더 (테스트·로컬 스모크, 네트워크 없음)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from market.providers.base import (
    ConstituentRow,
    DailyPriceBar,
    MarketDataProvider,
    MarketMetadataRow,
)


class StubMarketProvider(MarketDataProvider):
    """고정 바 생성: 각 심볼별로 trade_date 하루씩 증가하는 close/adj."""

    def __init__(
        self,
        *,
        base_close: float = 100.0,
        daily_drift: float = 0.001,
        constituents: Mapping[str, list[ConstituentRow]] | None = None,
    ) -> None:
        self._base_close = base_close
        self._daily_drift = daily_drift
        self._constituents: dict[str, list[ConstituentRow]] = dict(constituents or {})
        self._constituents.setdefault(
            "sp500_current",
            [
                ConstituentRow(symbol="AAA", name="Alpha", cik="0000000001"),
                ConstituentRow(symbol="BBB", name="Beta", cik="0000000002"),
            ],
        )

    def fetch_daily_prices(
        self,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
    ) -> list[DailyPriceBar]:
        out: list[DailyPriceBar] = []
        d = start_date
        i = 0
        while d <= end_date:
            if d.weekday() < 5:
                for sym in symbols:
                    u = sym.upper().strip()
                    c = self._base_close * ((1.0 + self._daily_drift) ** i)
                    out.append(
                        DailyPriceBar(
                            symbol=u,
                            trade_date=d,
                            open=c,
                            high=c * 1.01,
                            low=c * 0.99,
                            close=c,
                            adjusted_close=c,
                            volume=1_000_000.0,
                            raw_payload={"stub": True},
                        )
                    )
                i += 1
            d += timedelta(days=1)
        return out

    def fetch_market_metadata(self, symbols: Sequence[str]) -> list[MarketMetadataRow]:
        today = date.today()
        rows: list[MarketMetadataRow] = []
        for sym in symbols:
            u = sym.upper().strip()
            rows.append(
                MarketMetadataRow(
                    symbol=u,
                    as_of_date=today,
                    market_cap=1e10,
                    avg_daily_volume=5e6,
                    exchange="STUB",
                    raw_payload={"stub": True},
                )
            )
        return rows

    def fetch_index_constituents(self, index_name: str) -> list[ConstituentRow]:
        return list(self._constituents.get(index_name, []))
