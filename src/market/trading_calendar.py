"""거래일 캘린더 MVP: 주말만 제외(미국 공휴일 미반영 — README 명시)."""

from __future__ import annotations

from datetime import date, timedelta


def next_weekday_strictly_after(anchor: date) -> date:
    """anchor 날짜 이후 첫 평일(월~금). 공시 당일 종가 사용 금지(no same-day)."""
    d = anchor + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def is_weekday(d: date) -> bool:
    return d.weekday() < 5
