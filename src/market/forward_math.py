"""
선행 수익률: adjusted_close 우선, 없으면 close.

horizon_type:
- next_month: 시작일 포함 이후 21거래일 뒤 종가까지
- next_quarter: 63거래일 뒤 종가까지

excess: 구간 거래일 수 n에 대해 평균 연율화 무위험 이자율 r_avg(%)
→ period_rf = (1 + r_avg/100)^(n/252) - 1
→ excess = (1 + raw) / (1 + period_rf) - 1

(단순화; README에 명시)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence


def sorted_price_series(
    rows: Sequence[dict[str, Any]],
) -> list[tuple[date, float, str]]:
    """DB silver 행: trade_date, adjusted_close, close."""
    xs: list[tuple[date, float, str]] = []
    for r in rows:
        td_raw = r.get("trade_date")
        if isinstance(td_raw, str):
            td = date.fromisoformat(td_raw[:10])
        else:
            continue
        adj = r.get("adjusted_close")
        cl = r.get("close")
        if adj is not None:
            xs.append((td, float(adj), "adjusted_close"))
        elif cl is not None:
            xs.append((td, float(cl), "close"))
    xs.sort(key=lambda x: x[0])
    return xs


def forward_return_over_trading_days(
    series: Sequence[tuple[date, float, str]],
    signal_date: date,
    trading_day_offset: int,
) -> tuple[date, date, float, dict[str, Any]] | None:
    """
    signal_date 이상 첫 거래일을 시작 종가로, 그로부터 offset 거래일 후 종가까지 수익률.
    offset=21 → 약 1개월, 63 → 약 1분기.
    """
    if trading_day_offset < 1:
        return None
    start_i = None
    for i, (d, _, _) in enumerate(series):
        if d >= signal_date:
            start_i = i
            break
    if start_i is None:
        return None
    end_i = start_i + trading_day_offset
    if end_i >= len(series):
        return None
    d0, p0, b0 = series[start_i]
    d1, p1, b1 = series[end_i]
    raw = p1 / p0 - 1.0
    basis = {
        "price_basis_start": b0,
        "price_basis_end": b1,
        "start_trade_date": d0.isoformat(),
        "end_trade_date": d1.isoformat(),
        "trading_sessions_spanned": end_i - start_i,
    }
    return d0, d1, raw, basis


def excess_return_simple(
    raw: float,
    *,
    num_trading_periods: int,
    annualized_rates_pct: Sequence[float],
) -> tuple[float, dict[str, Any]]:
    """평균 연율화(%) → 복리 근사."""
    if not annualized_rates_pct:
        return raw, {"excess_method": "no_risk_free_data", "fallback": "raw_only"}
    r_avg = sum(annualized_rates_pct) / len(annualized_rates_pct)
    n = max(1, num_trading_periods)
    period_rf = (1.0 + r_avg / 100.0) ** (n / 252.0) - 1.0
    ex = (1.0 + raw) / (1.0 + period_rf) - 1.0 if period_rf != -1.0 else raw
    meta = {
        "excess_method": "avg_annualized_to_period_compound",
        "avg_annualized_risk_free_pct": r_avg,
        "trading_periods_for_exponent": n,
    }
    return ex, meta
