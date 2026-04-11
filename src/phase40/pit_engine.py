"""Shared PIT outcome classification and rollups (dynamic spec keys)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from research_validation.metrics import safe_float

from phase38.pit_join_logic import pick_state_change_at_or_before_signal, pit_safe_pick

STANDARD_BUCKETS = (
    "still_join_key_mismatch",
    "reclassified_to_joined",
    "reclassified_to_other_exclusion",
    "invalid_due_to_leakage_or_non_pit",
)


def add_calendar_days(signal_yyyy_mm_dd: str, days: int) -> str:
    d = date.fromisoformat(signal_yyyy_mm_dd[:10])
    return (d + timedelta(days=days)).isoformat()


def classify_row_outcome(
    picked: dict[str, Any] | None,
    reason: str,
    *,
    signal_bound: str,
) -> tuple[str, dict[str, Any]]:
    if reason == "state_change_built_but_join_key_mismatch":
        return "still_join_key_mismatch", {"pick_reason": reason}
    if reason == "state_change_not_built_for_row":
        return "reclassified_to_other_exclusion", {"pick_reason": reason}
    if reason != "picked" or picked is None:
        return "reclassified_to_other_exclusion", {"pick_reason": reason}
    ok, why = pit_safe_pick(picked, signal_bound=signal_bound)
    if not ok:
        return "invalid_due_to_leakage_or_non_pit", {"leakage_detail": why}
    sc = safe_float(picked.get("state_change_score_v1"))
    if sc is not None:
        return "reclassified_to_joined", {
            "picked_as_of": str(picked.get("as_of_date") or "")[:10],
        }
    return "reclassified_to_other_exclusion", {
        "detail": "missing_state_change_score_v1_after_pick",
        "picked_as_of": str(picked.get("as_of_date") or "")[:10],
    }


def rollup_standard(spec_results: dict[str, Any]) -> dict[str, int]:
    c = {k: 0 for k in STANDARD_BUCKETS}
    for _sk, cell in spec_results.items():
        if not isinstance(cell, dict):
            continue
        oc = str(cell.get("outcome_category") or "")
        if oc == "alternate_spec_not_executed":
            continue
        if oc in c:
            c[oc] += 1
    return c


def count_joined_in_family(row_results: list[dict[str, Any]]) -> int:
    n = 0
    for r in row_results:
        specs = r.get("spec_results") or {}
        if not isinstance(specs, dict):
            continue
        for cell in specs.values():
            if isinstance(cell, dict) and str(cell.get("outcome_category") or "") == "reclassified_to_joined":
                n += 1
                break
    return n


def iso_date_prefix(ts: str | None) -> str:
    if not ts:
        return ""
    s = str(ts).strip()
    if len(s) >= 10:
        return s[:10]
    return s
