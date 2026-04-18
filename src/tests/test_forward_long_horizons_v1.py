"""Pragmatic Brain Absorption v1 — Milestone A (Real horizon closure).

Covers the new next_half_year / next_year horizons end-to-end at the unit
level: forward-return loop, validation-panel builder, validation runner, and
validation factor registry.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from market.forward_math import forward_return_over_trading_days
from market.forward_returns_run import (
    FORWARD_HORIZON_SPECS,
    H_NEXT_HALF_YEAR,
    H_NEXT_MONTH,
    H_NEXT_QUARTER,
    H_NEXT_YEAR,
    TRADING_DAYS_1M,
    TRADING_DAYS_1Q,
    TRADING_DAYS_1Y,
    TRADING_DAYS_6M,
)
from research.validation_registry import VALIDATION_FACTORS_V1
from research.validation_runner import HORIZON_RETURN_KEYS


def test_forward_horizon_specs_cover_four_targets() -> None:
    horizons = {h for h, _ in FORWARD_HORIZON_SPECS}
    assert horizons == {H_NEXT_MONTH, H_NEXT_QUARTER, H_NEXT_HALF_YEAR, H_NEXT_YEAR}
    offsets = dict(FORWARD_HORIZON_SPECS)
    assert offsets[H_NEXT_MONTH] == TRADING_DAYS_1M == 21
    assert offsets[H_NEXT_QUARTER] == TRADING_DAYS_1Q == 63
    assert offsets[H_NEXT_HALF_YEAR] == TRADING_DAYS_6M == 126
    assert offsets[H_NEXT_YEAR] == TRADING_DAYS_1Y == 252


def test_forward_return_supports_long_horizon_offsets() -> None:
    base = date(2024, 1, 2)
    series: list[tuple[date, float, str]] = []
    d = base
    i = 0
    while len(series) < 300:
        if d.weekday() < 5:
            series.append((d, 100.0 + i * 0.1, "adjusted_close"))
            i += 1
        d += timedelta(days=1)
    sig = series[0][0]
    for htype, off in FORWARD_HORIZON_SPECS:
        fr = forward_return_over_trading_days(series, sig, off)
        assert fr is not None, f"forward return should be available for {htype}"
        assert int(fr[3]["trading_sessions_spanned"]) == off


def test_horizon_return_keys_expose_all_four_horizons() -> None:
    assert set(HORIZON_RETURN_KEYS.keys()) == {
        "next_month",
        "next_quarter",
        "next_half_year",
        "next_year",
    }
    assert HORIZON_RETURN_KEYS["next_half_year"] == ("raw_return_6m", "excess_return_6m")
    assert HORIZON_RETURN_KEYS["next_year"] == ("raw_return_1y", "excess_return_1y")


def test_validation_factors_v1_support_all_four_horizons() -> None:
    for spec in VALIDATION_FACTORS_V1:
        assert set(spec.supported_horizons) >= {
            "next_month",
            "next_quarter",
            "next_half_year",
            "next_year",
        }, f"{spec.factor_name} must opt into long horizons for Milestone A"


def test_validation_panel_run_writes_long_horizon_columns(monkeypatch) -> None:
    """Regression: panel upsert row shape must carry raw_return_6m / 1y columns."""
    from market import validation_panel_run as vpr

    captured_rows: list[dict[str, Any]] = []

    def fake_ticker(_client, *, cik):  # noqa: ANN001
        return "AAPL" if cik else None

    def fake_snapshot(_client, *, cik, accession_no):  # noqa: ANN001
        return {
            "cik": cik,
            "accession_no": accession_no,
            "accepted_at": "2024-06-03T22:10:00+00:00",
        }

    def fake_metadata(_client, *, symbol):  # noqa: ANN001
        return {"market_cap": 100.0, "avg_daily_volume": 1.0, "as_of_date": "2024-06-03"}

    def fake_forward_map(_client, *, symbol, signal_date):  # noqa: ANN001
        return {
            "next_month": {"raw_forward_return": 0.01, "excess_forward_return": 0.009},
            "next_quarter": {"raw_forward_return": 0.02, "excess_forward_return": 0.018},
            "next_half_year": {"raw_forward_return": 0.03, "excess_forward_return": 0.027},
            "next_year": {"raw_forward_return": 0.04, "excess_forward_return": 0.036},
        }

    def fake_upsert(_client, row):  # noqa: ANN001
        captured_rows.append(dict(row))

    def fake_finalize(_client, **_kwargs):  # noqa: ANN001
        return None

    monkeypatch.setattr(vpr, "fetch_ticker_for_cik", fake_ticker)
    monkeypatch.setattr(vpr, "fetch_quarter_snapshot_by_accession", fake_snapshot)
    monkeypatch.setattr(vpr, "fetch_market_metadata_latest_row_deterministic", fake_metadata)
    monkeypatch.setattr(vpr, "_fetch_forward_map", fake_forward_map)
    monkeypatch.setattr(vpr, "upsert_factor_market_validation_panel", fake_upsert)
    monkeypatch.setattr(vpr, "ingest_run_finalize", fake_finalize)

    panels = [
        {
            "id": "fp-1",
            "cik": "0000123",
            "accession_no": "0000123-24-001",
            "fiscal_year": 2024,
            "fiscal_period": "Q1",
            "factor_version": "v1",
        }
    ]
    result = vpr._validation_panel_build_loop(client=object(), run_id="run-x", panels=panels)

    assert result["status"] == "completed"
    assert result["rows_upserted"] == 1
    assert len(captured_rows) == 1
    row = captured_rows[0]
    assert row["raw_return_1m"] == 0.01
    assert row["raw_return_1q"] == 0.02
    assert row["raw_return_6m"] == 0.03
    assert row["excess_return_6m"] == 0.027
    assert row["raw_return_1y"] == 0.04
    assert row["excess_return_1y"] == 0.036
