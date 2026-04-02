"""Backfill 오케스트레이션 단위 테스트 (네트워크·DB 없음)."""

from __future__ import annotations

import pytest

from backfill import STAGE_ORDER
from backfill.backfill_runner import _stage_range
from backfill.join_diagnostics import build_join_diagnostics
from backfill.normalize import normalize_ticker_list, pad_cik_10
from backfill.pilot_tickers import load_pilot_tickers_v1
from backfill.universe_resolver import resolve_backfill_tickers


def test_stage_order_unique_and_resolve_first() -> None:
    assert STAGE_ORDER[0] == "resolve"
    assert len(STAGE_ORDER) == len(set(STAGE_ORDER))


def test_stage_range_sec_to_factors() -> None:
    lo, hi = _stage_range("sec", "factors")
    assert STAGE_ORDER[lo] == "sec"
    assert STAGE_ORDER[hi] == "factors"
    assert lo <= hi


def test_stage_range_invalid() -> None:
    with pytest.raises(ValueError):
        _stage_range("factors", "sec")


def test_normalize_ticker_list_dedupe() -> None:
    assert normalize_ticker_list(["aapl", " AAPL ", "MSFT"]) == ["AAPL", "MSFT"]


def test_pad_cik_10() -> None:
    assert pad_cik_10("1045810") == "0001045810"
    assert pad_cik_10("") == ""


def test_pilot_tickers_load() -> None:
    xs = load_pilot_tickers_v1()
    assert len(xs) >= 20
    assert all(t == t.upper() for t in xs)


def test_resolve_smoke_uses_fallback_when_universe_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def _empty(_client: object, _universe: str) -> list[str]:
        return []

    monkeypatch.setattr(
        "backfill.universe_resolver.resolve_slice_symbols",
        _empty,
    )
    tickers, meta = resolve_backfill_tickers(
        object(),
        mode="smoke",
        universe_name="sp500_current",
    )
    assert len(tickers) >= 3
    assert meta.get("mode") == "smoke"


def test_join_diagnostics_stub_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backfill.join_diagnostics.fetch_cik_for_ticker",
        lambda client, ticker: "0000320193",
    )

    class _E:
        def __init__(self, data: list) -> None:
            self._data = data

        def execute(self) -> object:
            return type("R", (), {"data": self._data})()

    class _T:
        def table(self, name: str) -> object:
            if name == "filing_index":
                return _Sel(_E([{"id": "1"}]))
            if name == "silver_xbrl_facts":
                return _Sel(_E([{"id": "1"}]))
            if name == "forward_returns_daily_horizons":
                return _SelFr(_E([{"cik": "0000320193"}]))
            if name == "issuer_quarter_factor_panels":
                return _Sel(_E([]))
            if name == "factor_market_validation_panels":
                return _Sel(_E([{"id": "1"}]))
            if name == "issuer_master":
                return _Sel(_E([{"ticker": "AAPL"}]))
            return _Sel(_E([]))

    class _Sel:
        def __init__(self, end: _E) -> None:
            self._end = end

        def select(self, *_a: object, **_k: object) -> "_Sel":
            return self

        def eq(self, *_a: object, **_k: object) -> "_Sel":
            return self

        def limit(self, *_a: object, **_k: object) -> _E:
            return self._end

    class _SelFr(_Sel):
        def limit(self, *_a: object, **_k: object) -> _E:
            return self._end

    out = build_join_diagnostics(_T(), symbols=["AAPL"])
    assert out["missing_issuer_master"] == []
    assert out["issuer_no_filing_index"] == []


def test_cli_help_backfill_commands() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    env = {**__import__("os").environ, "PYTHONPATH": str(root / "src")}
    for cmd in ("smoke-backfill", "backfill-universe", "report-backfill-status"):
        r = subprocess.run(
            [sys.executable, str(root / "src" / "main.py"), cmd, "-h"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 0, r.stderr
