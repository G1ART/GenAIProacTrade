"""Phase 4: provider, universe policy, 가격 정규화, 선행수익률, 패널 조인 (네트워크 없음)."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pytest

from market.candidate_universe_build import _load_seed
from market.forward_math import (
    excess_return_simple,
    forward_return_over_trading_days,
    sorted_price_series,
)
from market.price_normalize import bars_to_silver_rows
from market.providers.base import DailyPriceBar, MarketDataProvider
from market.providers.stub_provider import StubMarketProvider
from market.providers.yahoo_chart_provider import parse_sp500_html
from market.signal_date import signal_available_date_from_snapshot
from market.trading_calendar import next_weekday_strictly_after
from market.validation_panel_run import _fetch_forward_map  # noqa: PLC2701 — 테스트용


def test_market_data_provider_is_abc() -> None:
    assert issubclass(StubMarketProvider, MarketDataProvider)
    p = StubMarketProvider()
    assert p.name == "StubMarketProvider"
    bars = p.fetch_daily_prices(["X"], date(2024, 1, 2), date(2024, 1, 5))
    assert bars
    assert bars[0].symbol == "X"
    assert bars[0].adjusted_close is not None


def test_parse_sp500_html_honest_table() -> None:
    html = """
    <table id="constituents" class="wikitable">
    <tr><th>Symbol</th><th>Security</th><th>CIK</th></tr>
    <tr><td>AAA</td><td>Alpha Inc</td><td>0000000001</td></tr>
    <tr><td>BBB</td><td>Beta Inc</td><td>0000000002</td></tr>
    </table>
    """
    rows = parse_sp500_html(html)
    syms = {r.symbol for r in rows}
    assert "AAA" in syms and "BBB" in syms


def test_proxy_candidate_naming_policy() -> None:
    from market.run_types import UNIVERSE_PROXY_CANDIDATES

    assert "proxy" in UNIVERSE_PROXY_CANDIDATES
    assert "official" not in UNIVERSE_PROXY_CANDIDATES.lower()


def test_signal_available_next_weekday() -> None:
    snap = {"accepted_at": "2024-01-15T22:00:00+00:00"}
    sig = signal_available_date_from_snapshot(snap)
    assert sig == next_weekday_strictly_after(date(2024, 1, 15))


def test_signal_fallback_filed_at() -> None:
    snap = {"filed_at": "2024-06-01T12:00:00+00:00"}
    sig = signal_available_date_from_snapshot(snap)
    assert sig.weekday() < 5


def test_bars_to_silver_daily_return_and_rerun_shape() -> None:
    d0 = date(2024, 1, 2)
    d1 = date(2024, 1, 3)
    bars = [
        DailyPriceBar("Z", d0, close=100.0, adjusted_close=100.0, raw_payload={}),
        DailyPriceBar("Z", d1, close=102.0, adjusted_close=102.0, raw_payload={}),
    ]
    rows = bars_to_silver_rows(bars, cik="1", source_name="stub")
    assert rows[0]["daily_return"] is None
    assert rows[1]["daily_return"] == pytest.approx(0.02)


def test_forward_return_1m_1q_and_excess() -> None:
    # 70일 연속 거래일 행 (테스트용 단순 시계열)
    base = date(2024, 1, 2)
    series: list[tuple[date, float, str]] = []
    d = base
    while len(series) < 80:
        if d.weekday() < 5:
            series.append((d, 100.0 + len(series) * 0.1, "adjusted_close"))
        d += timedelta(days=1)
    sig = series[0][0]
    fr1 = forward_return_over_trading_days(series, sig, 21)
    fr2 = forward_return_over_trading_days(series, sig, 63)
    assert fr1 is not None and fr2 is not None
    raw1 = fr1[2]
    n = int(fr1[3]["trading_sessions_spanned"])
    ex, meta = excess_return_simple(raw1, num_trading_periods=n, annualized_rates_pct=[4.0])
    assert "excess_method" in meta
    assert ex != raw1 or meta.get("excess_method") == "no_risk_free_data"


def test_sorted_price_series_from_db_shape() -> None:
    rows = [
        {"trade_date": "2024-01-05", "adjusted_close": 10.0, "close": 10.0},
        {"trade_date": "2024-01-04", "adjusted_close": 9.0, "close": 9.0},
    ]
    s = sorted_price_series(rows)
    assert s[0][0] < s[1][0]


def test_load_seed(tmp_path) -> None:
    p = tmp_path / "s.json"
    p.write_text('{"symbols": ["A", "b"]}', encoding="utf-8")
    assert _load_seed(p) == ["A", "B"]


def test_cli_has_phase4_commands() -> None:
    from main import build_parser

    p = build_parser()
    choices: set[str] = set()
    for action in p._actions:
        if isinstance(action, argparse._SubParsersAction):
            choices = set(action.choices.keys())
            break
    for cmd in (
        "refresh-universe",
        "build-candidate-universe",
        "ingest-market-prices",
        "refresh-market-metadata",
        "ingest-risk-free",
        "build-forward-returns",
        "build-validation-panel",
        "smoke-market",
        "smoke-validation",
    ):
        assert cmd in choices


def test_fetch_forward_map_requires_client(monkeypatch) -> None:
    class C:
        def table(self, _name):
            return self

        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            class R:
                data = [
                    {
                        "horizon_type": "next_month",
                        "raw_forward_return": 0.01,
                        "excess_forward_return": 0.008,
                    }
                ]

            return R()

    m = _fetch_forward_map(C(), symbol="A", signal_date="2024-01-02")
    assert "next_month" in m
