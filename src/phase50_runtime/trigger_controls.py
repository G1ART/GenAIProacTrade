"""Merge budget policy with control-plane trigger allow/deny lists."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from phase48_runtime.budget_policy import default_budget_policy

from phase50_runtime.control_plane import DEFAULT_ALLOWED


def effective_budget_policy(control_plane: dict[str, Any]) -> dict[str, Any]:
    """Return a new policy dict with allowed_trigger_types intersected with control plane."""
    base = deepcopy(default_budget_policy())
    allowed_cp = list(control_plane.get("allowed_trigger_types") or DEFAULT_ALLOWED)
    disabled = set(control_plane.get("disabled_trigger_types") or [])
    base_all = set(allowed_cp) - disabled
    # Keep only types that exist in default union (governance)
    universe = set(DEFAULT_ALLOWED)
    merged = sorted(base_all & universe)
    if not merged:
        merged = ["manual_watchlist"]
    base["allowed_trigger_types"] = merged
    return base


def trigger_controls_summary(control_plane: dict[str, Any]) -> dict[str, Any]:
    pol = effective_budget_policy(control_plane)
    return {
        "allowed_trigger_types_effective": pol["allowed_trigger_types"],
        "disabled_trigger_types_config": list(control_plane.get("disabled_trigger_types") or []),
        "allowed_trigger_types_config": list(control_plane.get("allowed_trigger_types") or []),
    }
