"""투명 합성 점수 — 가중·누락 분리."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Optional


def population_zscores(values: list[float]) -> Optional[list[float]]:
    if len(values) < 2:
        return None
    mu = statistics.mean(values)
    sd = statistics.pstdev(values)
    if sd <= 1e-12:
        return None
    return [(v - mu) / sd for v in values]


@dataclass
class SubScoreParts:
    level: Optional[float]
    velocity: Optional[float]
    acceleration: Optional[float]
    persistence: Optional[float]
    contamination: Optional[float]
    regime_fit: Optional[float]


def weighted_composite(parts: SubScoreParts, *, base_weights: dict[str, float]) -> tuple[float, float, list[str]]:
    """
    Returns (score, normalized_weight_sum, included_keys).
    누락(None) 항목은 가중치에서 제외.
    """
    mapping = [
        ("level", parts.level, base_weights["level"]),
        ("velocity", parts.velocity, base_weights["velocity"]),
        ("acceleration", parts.acceleration, base_weights["acceleration"]),
        ("persistence", parts.persistence, base_weights["persistence"]),
        ("contamination", parts.contamination, base_weights.get("contamination", 0.0)),
        ("regime_fit", parts.regime_fit, base_weights.get("regime_fit", 0.0)),
    ]
    num = 0.0
    den = 0.0
    inc: list[str] = []
    for name, val, w in mapping:
        if val is None or w <= 0:
            continue
        if not math.isfinite(val):
            continue
        num += w * float(val)
        den += w
        inc.append(name)
    if den <= 0:
        return 0.0, 0.0, []
    return num / den, den, inc


def direction_from_score(score: float) -> str:
    if score > 0.12:
        return "strengthening"
    if score < -0.12:
        return "weakening"
    if abs(score) < 0.04:
        return "flat"
    return "mixed"


def confidence_band(
    *,
    included: int,
    missing: int,
    coverage_avg: float,
) -> str:
    if missing == 0 and included >= 3 and coverage_avg >= 0.85:
        return "high"
    if missing <= 2 and included >= 2 and coverage_avg >= 0.6:
        return "medium"
    return "low"


def gating_status(
    *,
    missing_component_count: int,
    coverage_avg: float,
    min_signals: int,
    signals_with_data: int,
) -> str:
    if signals_with_data < min_signals:
        return "insufficient_data"
    if coverage_avg < 0.35:
        return "low_coverage"
    if missing_component_count > 8:
        return "high_missingness"
    return "ok"


def top_drivers(
    contributions: list[tuple[str, float]],
    *,
    k: int = 5,
) -> list[dict[str, Any]]:
    ranked = sorted(contributions, key=lambda x: abs(x[1]), reverse=True)
    return [{"signal": a, "weighted_contribution": round(b, 6)} for a, b in ranked[:k]]


def resolve_component_weights(*, has_contamination: bool, has_regime: bool) -> dict[str, float]:
    w = {
        "level": 0.25,
        "velocity": 0.25,
        "acceleration": 0.25,
        "persistence": 0.25,
        "contamination": 0.0,
        "regime_fit": 0.0,
    }
    extra = 0.0
    if has_regime:
        w["regime_fit"] = 0.15
        extra += 0.15
    if has_contamination:
        w["contamination"] = 0.10
        extra += 0.10
    if extra > 0:
        scale = 1.0 - extra
        for k in ("level", "velocity", "acceleration", "persistence"):
            w[k] *= scale
    return w
