"""Market data provider interface. Factor/validation 코드는 구현체에 직접 의존하지 않는다."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class DailyPriceBar:
    symbol: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adjusted_close: float | None = None
    volume: float | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketMetadataRow:
    symbol: str
    as_of_date: date
    market_cap: float | None = None
    shares_outstanding: float | None = None
    avg_daily_volume: float | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstituentRow:
    symbol: str
    name: str | None = None
    cik: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


class MarketDataProvider(ABC):
    """가격·메타·지수 구성 종목 조회. 구현체는 HTTP/API 세부에 국한된다."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def fetch_daily_prices(
        self,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
    ) -> list[DailyPriceBar]:
        """일별 OHLCV (가능하면 adjusted_close 포함)."""

    @abstractmethod
    def fetch_market_metadata(self, symbols: Sequence[str]) -> list[MarketMetadataRow]:
        """심볼별 최신 메타(제공 범위 내). 없으면 빈 리스트 허용."""

    @abstractmethod
    def fetch_index_constituents(self, index_name: str) -> list[ConstituentRow]:
        """
        index_name 예: sp500_current → 현재 S&P 500 구성 목록.
        알 수 없는 index_name 은 빈 리스트.
        """

    def fetch_corporate_actions(
        self,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """옵션. MVP 기본은 미구현(빈 리스트)."""
        return []
