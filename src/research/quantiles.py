"""
팩터 분위(기본 5) — 기술적 기술통계만. 포트폴리오·전략 수익 아님.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple


@dataclass
class QuantileBucket:
    quantile_index: int
    indices: List[int]
    factors: List[float]
    raw_returns: List[float]
    excess_returns: List[float]


def choose_quantile_count(n_obs: int, preferred: int = 5) -> Optional[int]:
    """표본이 너무 작으면 분위 수 축소; 2 미만이면 None (스킵)."""
    if n_obs < 2:
        return None
    if n_obs < preferred:
        q = max(2, n_obs // 2)
        return q if q >= 2 else None
    return preferred


def assign_quantile_indices(values: Sequence[float], n_q: int) -> Optional[List[int]]:
    """각 관측의 분위 인덱스 0..n_q-1. 동액 값은 순서 보존 안정 분할."""
    n = len(values)
    if n_q < 2 or n < n_q:
        return None
    idx_order = sorted(range(n), key=lambda i: values[i])
    bins: List[int] = [0] * n
    for rank, pos in enumerate(idx_order):
        bins[pos] = min(n_q - 1, rank * n_q // n)
    return bins


def build_quantile_buckets(
    factors: List[float],
    raw_returns: List[float],
    excess_returns: List[float],
    *,
    n_quantiles: int = 5,
) -> Tuple[Optional[List[QuantileBucket]], dict[str, Any]]:
    """
    동일 길이 배열에 대해 분위 버킷 구성.
    실패 시 (None, {"reason": ...}).
    """
    n = len(factors)
    if n != len(raw_returns) or n != len(excess_returns):
        return None, {"reason": "length_mismatch"}
    n_q = choose_quantile_count(n, n_quantiles)
    if n_q is None:
        return None, {"reason": "insufficient_sample", "n": n}
    assigned = assign_quantile_indices(factors, n_q)
    if not assigned:
        return None, {"reason": "quantile_assignment_failed", "n": n, "n_quantiles": n_q}
    buckets: dict[int, list[int]] = {i: [] for i in range(n_q)}
    for i, b in enumerate(assigned):
        buckets[b].append(i)
    out: List[QuantileBucket] = []
    for qi in range(n_q):
        inds = buckets[qi]
        fs = [factors[i] for i in inds]
        rr = [raw_returns[i] for i in inds]
        er = [excess_returns[i] for i in inds]
        out.append(
            QuantileBucket(
                quantile_index=qi,
                indices=inds,
                factors=fs,
                raw_returns=rr,
                excess_returns=er,
            )
        )
    return out, {"n_quantiles": n_q, "n_obs": n}


def bucket_descriptive_spread(
    buckets: Sequence[QuantileBucket],
    *,
    return_basis: str,
) -> dict[str, Any]:
    """
    최고/최저 분위 평균 수익 차이 — 기술적 spread만. alpha/전략 표현 금지.
    """
    if not buckets:
        return {"top_bottom_spread": None, "note": "no_buckets"}
    def avg_ret(b: QuantileBucket) -> Optional[float]:
        rs = b.raw_returns if return_basis == "raw" else b.excess_returns
        clean = [x for x in rs if x is not None and not (isinstance(x, float) and str(x) == "nan")]
        if not clean:
            return None
        return float(statistics.mean(clean))

    top = avg_ret(buckets[-1])
    bottom = avg_ret(buckets[0])
    spread = None if top is None or bottom is None else top - bottom
    return {
        "descriptive_spread_top_minus_bottom": spread,
        "top_quantile_index": buckets[-1].quantile_index,
        "bottom_quantile_index": buckets[0].quantile_index,
        "label": "descriptive_only_not_strategy_return",
    }
