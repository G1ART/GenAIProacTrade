"""
결정적 기술 지표 — p-value·과도한 추론 없음. OLS는 보조(simple).
"""

from __future__ import annotations

import math
from typing import Any, Optional


def pearson_correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n != len(ys) or n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _average_ranks(values: list[float]) -> list[float]:
    """동점은 평균 순위(1-based)."""
    n = len(values)
    sorted_idx = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        v = values[sorted_idx[i]]
        while j + 1 < n and values[sorted_idx[j + 1]] == v:
            j += 1
        # 1-based ranks i+1 .. j+1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_idx[k]] = avg
        i = j + 1
    return ranks


def spearman_rank_correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = _average_ranks(xs)
    ry = _average_ranks(ys)
    return pearson_correlation(rx, ry)


def hit_rate_same_sign(factors: list[float], returns: list[float]) -> Optional[float]:
    """
    둘 다 유한이고 return != 0 인 쌍만 대상으로 (factor>0)==(return>0) 비율.
    return==0 인 관측은 제외(방향 불명).
    """
    eligible = 0
    same = 0
    for f, r in zip(factors, returns):
        if not (math.isfinite(f) and math.isfinite(r)):
            continue
        if r == 0:
            continue
        eligible += 1
        if (f > 0) == (r > 0):
            same += 1
    if eligible == 0:
        return None
    return same / eligible


def ols_simple_slope_intercept(xs: list[float], ys: list[float]) -> Optional[dict[str, Any]]:
    """
    y ~ a + b*x. Robust SE·패널·Fama-MacBeth 미구현(README 참고).
    """
    n = len(xs)
    if n != len(ys) or n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((ys[i] - my) ** 2 for i in range(n))
    if ss_tot == 0:
        r2 = None
    else:
        pred = [a + b * xs[i] for i in range(n)]
        ss_res = sum((ys[i] - pred[i]) ** 2 for i in range(n))
        r2 = 1.0 - ss_res / ss_tot if ss_tot else None
    return {
        "intercept": a,
        "slope": b,
        "n": n,
        "r_squared": r2,
        "x_label": "factor_value",
        "method": "simple_ols",
        "not_implemented": ["robust_se", "panel_regression", "fama_macbeth"],
    }
