"""Map exclusion reasons to repair actions and JSON action queue rows."""

from __future__ import annotations

from typing import Any

from public_buildout.constants import SUGGESTED_ACTION_BY_REASON, TRACKED_EXCLUSION_KEYS


def build_action_queue_json(
    exclusion_dist: dict[str, int],
    symbol_queues: dict[str, list[str]],
    *,
    repair_status: str = "pending",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for reason in TRACKED_EXCLUSION_KEYS:
        n = int(exclusion_dist.get(reason, 0))
        if n <= 0:
            continue
        syms = list(symbol_queues.get(reason) or [])
        out.append(
            {
                "reason": reason,
                "affected_symbol_count": n,
                "symbols_sample": syms[:500],
                "symbols_truncated": len(syms) > 500,
                "suggested_action": SUGGESTED_ACTION_BY_REASON.get(reason, "unknown"),
                "repair_status": repair_status,
            }
        )
    out.sort(key=lambda x: (-x["affected_symbol_count"], x["reason"]))
    return out
