"""Named cycle profiles and scheduler-readable run/skip decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TIMING_PROFILES: dict[str, dict[str, Any]] = {
    "manual_debug": {
        "description": "Operator-invoked; minimal cadence gating.",
        "min_interval_seconds": 0,
        "respect_window_cap": False,
    },
    "low_cost_polling": {
        "description": "Periodic polling with conservative minimum spacing.",
        "min_interval_seconds": 60,
        "respect_window_cap": True,
    },
    "alert_sensitive": {
        "description": "Shorter interval when alert-driven paths are enabled.",
        "min_interval_seconds": 15,
        "respect_window_cap": True,
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def should_run_cycle_now(
    *,
    control_plane: dict[str, Any],
    profile_name: str | None,
    last_cycle_started_at: str | None,
    cycles_in_current_window: int,
) -> dict[str, Any]:
    """Deterministic decision for whether a cycle may start."""
    if not control_plane.get("enabled", True):
        return {"run": False, "reason": "runtime_disabled", "detail": _now_iso()}
    if control_plane.get("maintenance_mode"):
        return {"run": False, "reason": "maintenance_mode", "detail": _now_iso()}

    pname = str(profile_name or control_plane.get("default_cycle_profile") or "low_cost_polling")
    prof = TIMING_PROFILES.get(pname) or TIMING_PROFILES["low_cost_polling"]
    max_win = int(control_plane.get("max_cycles_per_window") or 120)
    win_sec = int(control_plane.get("window_seconds") or 3600)

    if prof.get("respect_window_cap", True) and cycles_in_current_window >= max_win:
        return {
            "run": False,
            "reason": "max_cycles_per_window_exceeded",
            "detail": f"count={cycles_in_current_window} window_s={win_sec} max={max_win}",
        }

    min_iv = int(prof.get("min_interval_seconds") or 0)
    if min_iv > 0 and last_cycle_started_at:
        try:
            last = datetime.fromisoformat(str(last_cycle_started_at).replace("Z", "+00:00"))
            delta = (datetime.now(timezone.utc) - last).total_seconds()
            if delta < min_iv:
                return {
                    "run": False,
                    "reason": "min_interval_not_elapsed",
                    "detail": f"need {min_iv}s elapsed={delta:.1f}s profile={pname}",
                }
        except ValueError:
            pass

    return {"run": True, "reason": "allowed", "detail": f"profile={pname}", "profile": pname}
