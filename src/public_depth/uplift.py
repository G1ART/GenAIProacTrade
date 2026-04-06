"""Before vs after numeric and quality-share deltas."""

from __future__ import annotations

from typing import Any

from public_depth.constants import UPLIFT_NUMERIC_KEYS, UPLIFT_SHARE_KEYS


def compute_uplift_metrics(
    before_metrics: dict[str, Any], after_metrics: dict[str, Any]
) -> dict[str, Any]:
    out: dict[str, Any] = {"deltas": {}, "before": {}, "after": {}}
    for k in UPLIFT_NUMERIC_KEYS:
        b = before_metrics.get(k)
        a = after_metrics.get(k)
        bv = int(b) if b is not None else 0
        av = int(a) if a is not None else 0
        out["before"][k] = bv
        out["after"][k] = av
        out["deltas"][k] = av - bv
    for k in UPLIFT_SHARE_KEYS:
        b = before_metrics.get(k)
        a = after_metrics.get(k)
        out["before"][k] = b
        out["after"][k] = a
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            out["deltas"][k] = float(a) - float(b)
        else:
            out["deltas"][k] = None
    thin_b = before_metrics.get("thin_input_share")
    thin_a = after_metrics.get("thin_input_share")
    if isinstance(thin_b, (int, float)) and isinstance(thin_a, (int, float)):
        out["thin_input_improved"] = float(thin_a) < float(thin_b)
    else:
        out["thin_input_improved"] = None
    jb = int(before_metrics.get("joined_recipe_substrate_row_count") or 0)
    ja = int(after_metrics.get("joined_recipe_substrate_row_count") or 0)
    out["joined_substrate_improved"] = ja > jb
    return out
