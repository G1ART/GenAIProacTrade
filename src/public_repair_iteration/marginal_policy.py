"""
Phase 22: deterministic marginal-return classification for public-depth iterations.

Thresholds align with Phase 20 plateau constants where noted; all cutoffs are explicit.
"""

from __future__ import annotations

from typing import Any

from public_repair_iteration.constants import (
    JOINED_PLATEAU_MAX_DELTA,
    JOINED_STRONG_IMPROVEMENT_DELTA,
    THIN_IMPROVEMENT_MIN_DROP,
)
from public_repair_iteration.infra_noise import classify_infra_failure

# --- Explicit classification thresholds (documented) ---

# Meaningful: same bar as escalation "strong joined" or material thin drop.
MEANINGFUL_JOINED_DELTA_MIN = JOINED_STRONG_IMPROVEMENT_DELTA
MEANINGFUL_THIN_DROP_MIN = THIN_IMPROVEMENT_MIN_DROP

# Marginal: strictly positive substrate move or any thin improvement, below meaningful bars.
MARGINAL_JOINED_DELTA_MIN = 1.0

# No material: substrate flat and thin flat (within noise).
NO_MATERIAL_JOINED_ABS_MAX = 0.0
NO_MATERIAL_THIN_ABS_DELTA_MAX = 0.003

# Degraded trend: thin worsened beyond this, or joined dropped.
DEGRADED_THIN_WORSEN_MIN = 0.01

IMPROVEMENT_CLASSIFICATIONS = frozenset(
    {
        "meaningful_progress",
        "marginal_progress",
        "no_material_progress",
        "degraded_or_noisy",
    }
)


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def classify_public_depth_improvement(ledger: dict[str, Any]) -> str:
    """
    Classify a single public-depth iteration ledger row.

    Expects numeric deltas and optional error_message / expansion_ok.
    """
    if not ledger.get("expansion_ok", True):
        msg = str(ledger.get("error_message") or "")
        if classify_infra_failure(msg):
            return "degraded_or_noisy"
        return "degraded_or_noisy"

    jd = _f(ledger.get("joined_recipe_substrate_row_count_delta"))
    td = _f(ledger.get("thin_input_share_delta"))

    if jd is not None and jd < 0:
        return "degraded_or_noisy"
    if td is not None and td >= DEGRADED_THIN_WORSEN_MIN:
        return "degraded_or_noisy"

    meaningful_joined = jd is not None and jd >= MEANINGFUL_JOINED_DELTA_MIN
    meaningful_thin = td is not None and td <= -MEANINGFUL_THIN_DROP_MIN
    if meaningful_joined or meaningful_thin:
        return "meaningful_progress"

    marginal_joined = jd is not None and jd >= MARGINAL_JOINED_DELTA_MIN
    marginal_thin = td is not None and td < 0
    if marginal_joined or marginal_thin:
        return "marginal_progress"

    no_j = jd is None or abs(jd) <= NO_MATERIAL_JOINED_ABS_MAX
    no_t = td is None or abs(td) <= NO_MATERIAL_THIN_ABS_DELTA_MAX
    if no_j and no_t:
        return "no_material_progress"

    return "marginal_progress"


def assert_improvement_classification(value: str) -> str:
    if value not in IMPROVEMENT_CLASSIFICATIONS:
        raise ValueError(f"invalid improvement classification: {value}")
    return value


def near_plateau_ledgers(
    ledgers_newest_first: list[dict[str, Any]],
    *,
    max_abs_joined_for_plateau: float = float(JOINED_PLATEAU_MAX_DELTA),
    streak: int = 2,
) -> bool:
    """True if the newest `streak` depth ledgers are flat on joined delta (|jd| <= cap)."""
    if len(ledgers_newest_first) < streak:
        return False
    for L in ledgers_newest_first[:streak]:
        jd = _f(L.get("joined_recipe_substrate_row_count_delta"))
        if jd is None or abs(jd) > max_abs_joined_for_plateau:
            return False
        cls = str(L.get("improvement_classification") or "")
        if cls not in ("no_material_progress", "marginal_progress"):
            return False
    return True
