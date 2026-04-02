"""
검증용 표준화 — truth layer 컬럼은 변경하지 않음. 연산용 파생값만.
"""

from __future__ import annotations

import statistics
from typing import List, Optional, Sequence


def zscore(values: Sequence[float]) -> List[Optional[float]]:
    """표본 표준편차 기준 z-score. 분산 0이면 전부 None."""
    xs = list(values)
    n = len(xs)
    if n < 2:
        return [None] * n
    m = statistics.mean(xs)
    try:
        sd = statistics.stdev(xs)
    except statistics.StatisticsError:
        return [None] * n
    if sd == 0 or not sd:
        return [None] * n
    return [(x - m) / sd for x in xs]


def winsorize(
    values: Sequence[float],
    *,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> List[float]:
    """
    분위 기준 winsorize. 기본 [1%, 99%] 구간으로 클립.
    README·호출부에서 범위를 명시할 것.
    """
    xs = sorted(float(x) for x in values)
    if not xs:
        return []
    n = len(xs)
    lo_i = min(n - 1, max(0, int(lower_pct * n)))
    hi_i = min(n - 1, max(0, int(upper_pct * (n - 1))))
    lo = xs[lo_i]
    hi = xs[hi_i]
    return [min(max(float(x), lo), hi) for x in values]
