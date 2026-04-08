"""Yahoo Finance chart API(비공식 JSON) + 위키백과 S&P 500 표. urllib만 사용."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Sequence

from market.http_tls import ssl_context_for_urllib
from market.providers.base import (
    ConstituentRow,
    DailyPriceBar,
    MarketDataProvider,
    MarketMetadataRow,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; GenAIProacTrade/1.0; +https://example.invalid)"
)


def _http_get_json(url: str, timeout: int = 45) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl_context_for_urllib()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _http_get_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl_context_for_urllib()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_yahoo_chart(symbol: str, payload: dict[str, Any]) -> list[DailyPriceBar]:
    sym_u = symbol.upper().strip()
    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    r0 = result[0]
    ts = r0.get("timestamp") or []
    ind = r0.get("indicators", {}) or {}
    quote = (ind.get("quote") or [{}])[0]
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []
    out: list[DailyPriceBar] = []
    for i, t in enumerate(ts):
        if t is None:
            continue
        td = datetime.fromtimestamp(int(t), tz=timezone.utc).date()
        c = closes[i] if i < len(closes) else None
        ac = adj[i] if adj and i < len(adj) else c
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        lo = lows[i] if i < len(lows) else None
        v = float(vols[i]) if i < len(vols) and vols[i] is not None else None
        out.append(
            DailyPriceBar(
                symbol=sym_u,
                trade_date=td,
                open=float(o) if o is not None else None,
                high=float(h) if h is not None else None,
                low=float(lo) if lo is not None else None,
                close=float(c) if c is not None else None,
                adjusted_close=float(ac) if ac is not None else None,
                volume=v,
                raw_payload={"yahoo_chart": True},
            )
        )
    return out


class _Sp500TableParser(HTMLParser):
    """위키 'S&P 500' 표에서 Symbol, Security, CIK 열 추출(간이)."""

    def __init__(self) -> None:
        super().__init__()
        self._in_table = False
        self._depth = 0
        self._row: list[str] = []
        self._cell = ""
        self._in_cell = False
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {str(k): (v or "") for k, v in attrs}
        if tag == "table" and ad.get("id") == "constituents":
            self._in_table = True
            self._depth = 0
        if not self._in_table:
            return
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell = ""

    def handle_endtag(self, tag: str) -> None:
        if not self._in_table:
            return
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            t = re.sub(r"\s+", " ", self._cell).strip()
            self._row.append(t)
        elif tag == "tr" and self._row:
            if len(self._row) >= 2 and self._row[0] != "Symbol":
                self.rows.append(self._row[:])
        elif tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell += data


def parse_sp500_html(html: str) -> list[ConstituentRow]:
    p = _Sp500TableParser()
    p.feed(html)
    p.close()
    out: list[ConstituentRow] = []
    for row in p.rows:
        sym = row[0].strip().upper()
        if not sym or sym == "SYMBOL":
            continue
        name = row[1] if len(row) > 1 else None
        cik = None
        for cell in row:
            m = re.fullmatch(r"\d{10}", cell.strip())
            if m:
                cik = m.group(0)
                break
        out.append(
            ConstituentRow(
                symbol=sym,
                name=name,
                cik=cik,
                raw_payload={"source": "wikipedia_sp500_table"},
            )
        )
    return out


class YahooChartMarketProvider(MarketDataProvider):
    """일봉: Yahoo chart API. 구성종목: 위키백과 표(비공식)."""

    @property
    def name(self) -> str:
        return "yahoo_chart"

    def fetch_daily_prices(
        self,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
    ) -> list[DailyPriceBar]:
        all_bars: list[DailyPriceBar] = []
        p1 = int(datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())
        p2 = int(datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())
        for sym in symbols:
            u = sym.upper().strip()
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(u)}"
                f"?period1={p1}&period2={p2}&interval=1d"
            )
            try:
                payload = _http_get_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
                logger.warning("yahoo chart 실패 %s: %s", u, e)
                continue
            all_bars.extend(_parse_yahoo_chart(u, payload))
        return all_bars

    def fetch_market_metadata(self, symbols: Sequence[str]) -> list[MarketMetadataRow]:
        """
        일봉 차트(약 60거래일)로 평균 거래량·최종 as_of_date·거래소 메타를 채운다.
        시총 등은 미제공(None). HTTP 실패·빈 차트 심볼은 건너뜀.
        """
        end_d = date.today()
        start_d = end_d - timedelta(days=75)
        p1 = int(
            datetime.combine(start_d, datetime.min.time())
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
        p2 = int(
            datetime.combine(end_d + timedelta(days=1), datetime.min.time())
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
        out: list[MarketMetadataRow] = []
        for sym in symbols:
            u = sym.upper().strip()
            if not u:
                continue
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(u)}"
                f"?period1={p1}&period2={p2}&interval=1d"
            )
            try:
                payload = _http_get_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
                logger.warning("yahoo chart metadata 실패 %s: %s", u, e)
                continue
            bars = _parse_yahoo_chart(u, payload)
            if not bars:
                continue
            vols = [b.volume for b in bars if b.volume is not None]
            avg_v = float(sum(vols)) / len(vols) if vols else None
            last = bars[-1]
            r0 = (payload.get("chart") or {}).get("result") or [{}]
            meta_extra = (r0[0].get("meta") if r0 else None) or {}
            exch = meta_extra.get("exchangeName") or meta_extra.get("fullExchangeName")
            out.append(
                MarketMetadataRow(
                    symbol=u,
                    as_of_date=last.trade_date,
                    market_cap=None,
                    shares_outstanding=None,
                    avg_daily_volume=avg_v,
                    exchange=str(exch) if exch else None,
                    sector=None,
                    industry=None,
                    raw_payload={
                        "yahoo_chart_metadata": True,
                        "bars_returned": len(bars),
                        "meta": meta_extra,
                    },
                )
            )
        return out

    def fetch_index_constituents(self, index_name: str) -> list[ConstituentRow]:
        if index_name != "sp500_current":
            return []
        wiki = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        try:
            html = _http_get_text(wiki)
        except (urllib.error.URLError, OSError) as e:
            logger.warning("wikipedia sp500 실패: %s", e)
            return []
        return parse_sp500_html(html)
