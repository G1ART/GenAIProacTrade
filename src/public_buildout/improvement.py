"""Before/after exclusion deltas and substrate uplift bundle."""

from __future__ import annotations

from typing import Any

from public_buildout.constants import TRACKED_EXCLUSION_KEYS
from public_depth.uplift import compute_uplift_metrics


def compute_exclusion_deltas(
    before_ex: dict[str, int], after_ex: dict[str, int]
) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for k in TRACKED_EXCLUSION_KEYS:
        b = int(before_ex.get(k, 0))
        a = int(after_ex.get(k, 0))
        rows[k] = {"before": b, "after": a, "delta": a - b, "reduced": a < b}
    return {"tracked": rows}


def compute_buildout_improvement_summary(
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    before_ex: dict[str, int],
    after_ex: dict[str, int],
) -> dict[str, Any]:
    return {
        "exclusion_improvement": compute_exclusion_deltas(before_ex, after_ex),
        "substrate_uplift": compute_uplift_metrics(before_metrics, after_metrics),
    }
