"""분기 정렬·as_of_date·lag 추출 (미래 라벨 미사용)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional


FP_ORDER: dict[str, int] = {
    "Q1": 1,
    "Q2": 2,
    "Q3": 3,
    "Q4": 4,
    "1Q": 1,
    "2Q": 2,
    "3Q": 3,
    "4Q": 4,
    "FY": 5,
}


def fiscal_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    fy = int(row.get("fiscal_year") or 0)
    fp = str(row.get("fiscal_period") or "").upper().strip()
    return (fy, FP_ORDER.get(fp, 99))


def ordered_panels_for_cik(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(panels, key=fiscal_sort_key)


def as_of_date_for_panel(panel: dict[str, Any], snapshot: dict[str, Any] | None) -> str:
    if snapshot and snapshot.get("period_end"):
        pe = snapshot["period_end"]
        return str(pe)[:10]
    fy = int(panel.get("fiscal_year") or 0)
    fp = str(panel.get("fiscal_period") or "").upper().strip()
    q = FP_ORDER.get(fp, 1)
    month_end = min(3 * q, 12)
    return f"{fy:04d}-{month_end:02d}-28"


def _finite(x: Any) -> bool:
    if x is None:
        return False
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def as_float(x: Any) -> Optional[float]:
    if not _finite(x):
        return None
    return float(x)


@dataclass
class LagSeries:
    current: Optional[float]
    lag_1: Optional[float]
    lag_2: Optional[float]
    lag_4: Optional[float]
    velocity: Optional[float]
    acceleration: Optional[float]
    vel_history: tuple[Optional[float], ...]


def build_lag_series(
    values: list[Optional[float]],
    index: int,
) -> LagSeries:
    cur = values[index] if 0 <= index < len(values) else None
    lag1 = values[index - 1] if index >= 1 else None
    lag2 = values[index - 2] if index >= 2 else None
    lag4 = values[index - 4] if index >= 4 else None

    def vel_at(i: int) -> Optional[float]:
        if i < 1 or i >= len(values):
            return None
        a, b = values[i], values[i - 1]
        if not _finite(a) or not _finite(b):
            return None
        return float(a) - float(b)

    v_now = vel_at(index)
    v_prev = vel_at(index - 1) if index >= 1 else None
    accel: Optional[float] = None
    if v_now is not None and v_prev is not None:
        accel = v_now - v_prev

    hist: list[Optional[float]] = []
    for j in range(index, max(-1, index - 5), -1):
        if j < 1:
            break
        hist.append(vel_at(j))
    hist.reverse()
    return LagSeries(
        current=cur,
        lag_1=lag1,
        lag_2=lag2,
        lag_4=lag4,
        velocity=v_now,
        acceleration=accel,
        vel_history=tuple(hist),
    )
