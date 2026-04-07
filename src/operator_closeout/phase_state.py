"""REST/schema smokes for post-patch phase gates (phase17–22 public stack)."""

from __future__ import annotations

from typing import Any, Callable

from db import records as dbrec

PhaseSmokeFn = Callable[[Any], None]

_SMOKE_CHAIN: list[tuple[str, PhaseSmokeFn]] = [
    ("phase17_public_depth", dbrec.smoke_phase17_public_depth_tables),
    ("phase18_public_buildout", dbrec.smoke_phase18_public_buildout_tables),
    ("phase19_public_repair_campaign", dbrec.smoke_phase19_public_repair_campaign_tables),
    ("phase20_repair_iteration", dbrec.smoke_phase20_repair_iteration_tables),
    ("phase21_iteration_governance", dbrec.smoke_phase21_iteration_governance),
    ("phase22_public_depth_iteration", dbrec.smoke_phase22_public_depth_iteration_members),
]


def verify_db_phase_state(client: Any) -> dict[str, Any]:
    """Run ordered smokes; first failure stops the chain (deterministic)."""
    results: list[dict[str, Any]] = []
    for phase_key, fn in _SMOKE_CHAIN:
        try:
            fn(client)
            results.append({"phase": phase_key, "ok": True})
        except Exception as e:  # noqa: BLE001
            results.append({"phase": phase_key, "ok": False, "error": str(e)})
            return {
                "ok": False,
                "failed_at": phase_key,
                "results": results,
                "hint": "Fix schema (apply migrations) or connectivity, then re-run verify-db-phase-state.",
            }
    return {"ok": True, "results": results}
