"""구성요소 점수: level / velocity / acceleration / persistence (+ nullable 오버레이)."""

from __future__ import annotations

import math
import statistics
from typing import Any, Optional

from state_change.signal_registry import StateChangeSignalSpec


def clip_z(z: float, cap: float = 3.0) -> float:
    if not math.isfinite(z):
        return 0.0
    return max(-cap, min(cap, z)) / cap


def apply_direction_level(z: float, spec: StateChangeSignalSpec) -> float:
    c = clip_z(z)
    if spec.preferred_direction == "higher_is_positive":
        return c
    if spec.preferred_direction == "lower_is_positive":
        return -c
    return 0.0


def apply_direction_delta(z_delta: float, spec: StateChangeSignalSpec) -> float:
    c = clip_z(z_delta)
    if spec.preferred_direction == "higher_is_positive":
        return c
    if spec.preferred_direction == "lower_is_positive":
        return -c
    return c


def persistence_score(velocities: tuple[Optional[float], ...]) -> Optional[float]:
    """
    same_sign_streak 정규화: 최근 velocity 부호 일관성 (0~1).
    """
    usable = [v for v in velocities if v is not None and math.isfinite(v) and abs(v) > 1e-12]
    if len(usable) < 2:
        return None
    signs = [1 if v > 0 else -1 for v in usable[-4:]]
    if not signs:
        return None
    first = signs[-1]
    streak = 1
    for s in reversed(signs[:-1]):
        if s == first:
            streak += 1
        else:
            break
    return min(1.0, streak / 4.0) * (1.0 if all(s == first for s in signs) else 0.5)


def coverage_ratio_for_signal(panel_row: dict[str, Any], signal_name: str) -> float:
    cov = panel_row.get("coverage_json") or {}
    fac = cov.get(signal_name)
    if isinstance(fac, dict) and fac.get("available") is False:
        return 0.0
    if isinstance(fac, dict) and isinstance(fac.get("ratio"), (int, float)):
        return max(0.0, min(1.0, float(fac["ratio"])))
    return 1.0


def contamination_placeholder(
    include_overlay: bool,
) -> tuple[Optional[float], dict[str, Any]]:
    """v1: 결정적 오염 proxy 없음 — null 유지, 메타만."""
    notes: dict[str, Any] = {
        "contamination_available": False,
        "contamination_missing_reason": "no_deterministic_proxy_v1",
    }
    if include_overlay:
        notes["include_nullable_overlays_requested"] = True
    return None, notes


def regime_fit_from_risk_free(
    rates: list[dict[str, Any]],
    *,
    as_of_date: str,
    include_overlay: bool,
) -> tuple[Optional[float], dict[str, Any]]:
    """
    risk_free_rates_daily 만 사용. 표본 부족 시 null (0과 구분).
    rates 는 호출 측에서 as_of_date 이전(포함)으로 이미 필터링된 것으로 둔다.
    """
    _ = include_overlay
    meta: dict[str, Any] = {"regime_source": "risk_free_rates_daily"}
    if len(rates) < 20:
        meta["regime_missing_reason"] = "insufficient_rate_history"
        return None, meta
    vals = []
    for row in rates:
        v = row.get("annualized_rate")
        if v is not None:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
    if len(vals) < 20:
        meta["regime_missing_reason"] = "insufficient_parsed_rates"
        return None, meta
    latest = vals[-1]
    mu = statistics.mean(vals[:-1]) if len(vals) > 1 else vals[0]
    sd = statistics.pstdev(vals[:-1]) if len(vals) > 2 else 0.0
    if sd <= 1e-12:
        meta["regime_missing_reason"] = "zero_variance"
        return None, meta
    z = (latest - mu) / sd
    meta["as_of_date"] = as_of_date
    meta["latest_rate"] = latest
    score = clip_z(z)
    return float(score), meta
