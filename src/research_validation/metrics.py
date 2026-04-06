"""Deterministic validation metrics: spreads, cohorts, windows."""

from __future__ import annotations

import math
import statistics
from typing import Any, Optional

from research_validation.constants import SPREAD_TAIL_FRAC


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def norm_signal_date(s: Any) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    if "T" in t:
        t = t.split("T", 1)[0]
    return t[:10] if len(t) >= 10 else None


def year_bucket(signal_date: Optional[str]) -> str:
    if not signal_date or len(signal_date) < 4:
        return "unknown_year"
    return signal_date[:4]


def state_change_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        cik = str(r.get("cik") or "").strip()
        ad = r.get("as_of_date")
        if not cik or ad is None:
            continue
        ds = str(ad)[:10]
        out[(cik, ds)] = r
    return out


def top_bottom_spread(pairs: list[tuple[float, float]], frac: float = SPREAD_TAIL_FRAC) -> Optional[float]:
    clean = [(s, y) for s, y in pairs if y is not None and math.isfinite(s) and math.isfinite(y)]
    if len(clean) < 12:
        return None
    clean.sort(key=lambda x: x[0])
    n = len(clean)
    k = max(2, int(n * frac))
    bottom_mean = statistics.mean(y for _, y in clean[:k])
    top_mean = statistics.mean(y for _, y in clean[-k:])
    return top_mean - bottom_mean


def size_tertile_labels(mcaps: list[Optional[float]]) -> list[str]:
    vals = [m for m in mcaps if m is not None and m > 0]
    if len(vals) < 9:
        return ["size_unknown"] * len(mcaps)
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    t1 = vals_sorted[n // 3]
    t2 = vals_sorted[(2 * n) // 3]
    out: list[str] = []
    for m in mcaps:
        if m is None or m <= 0:
            out.append("size_unknown")
        elif m <= t1:
            out.append("size_small")
        elif m <= t2:
            out.append("size_mid")
        else:
            out.append("size_large")
    return out


def recipe_score_from_hypothesis(
    families: set[str],
    *,
    state_change_score: float,
    avg_daily_volume: Optional[float],
    missing_component_count: int,
) -> float:
    mod = 0.0
    if "liquidity_proxy" in families or "forward_excess_next_quarter" in families:
        v = avg_daily_volume or 0.0
        slow = 1.0 / (1.0 + math.log1p(max(v, 1.0)))
        mod += 0.08 * slow
    if "disclosure_complexity_proxy" in families:
        mod -= 0.04 * min(8.0, float(missing_component_count) + 1.0)
    if "missing_component_count" in families or "gating_status" in families:
        mod -= 0.12 * min(6.0, float(missing_component_count))
    return state_change_score + mod


def mcap_baseline_score(mcap: Optional[float]) -> float:
    if mcap is None or mcap <= 0:
        return 0.0
    return -math.log(mcap)
