"""Deterministic state_change pick — mirrors Phase 36 residual join (production-equivalent)."""

from __future__ import annotations

import bisect
from typing import Any

from research_validation.metrics import norm_cik


def pick_state_change_at_or_before_signal(
    sc_by_cik: dict[str, list[tuple[str, dict[str, Any]]]],
    *,
    cik: str,
    signal_date: str,
) -> tuple[dict[str, Any] | None, str]:
    """
    Returns (picked_row_or_none, reason).
    reason: picked | state_change_not_built_for_row | state_change_built_but_join_key_mismatch
    """
    ck = norm_cik(cik)
    pairs = sc_by_cik.get(ck)
    if not pairs:
        return None, "state_change_not_built_for_row"
    dates = [p[0] for p in pairs]
    idx = bisect.bisect_right(dates, signal_date) - 1
    if idx < 0:
        return None, "state_change_built_but_join_key_mismatch"
    return pairs[idx][1], "picked"


def pit_safe_pick(
    picked: dict[str, Any] | None,
    *,
    signal_bound: str,
) -> tuple[bool, str]:
    """True if no pick or picked as_of_date <= signal_bound (YYYY-MM-DD)."""
    if picked is None:
        return True, "no_pick"
    ad = str(picked.get("as_of_date") or "")[:10]
    if len(ad) < 10:
        return False, "invalid_as_of_on_row"
    if ad > signal_bound[:10]:
        return False, "pick_after_signal_bound"
    return True, "ok"
