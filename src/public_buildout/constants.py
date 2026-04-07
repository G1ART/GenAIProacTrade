"""Phase 18: targeted public substrate build-out."""

from __future__ import annotations

from research_validation.constants import MIN_SAMPLE_ROWS

POLICY_VERSION = "phase18_v1"

TRACKED_EXCLUSION_KEYS = (
    "no_validation_panel_for_symbol",
    "no_state_change_join",
    "missing_excess_return_1q",
)

SUGGESTED_ACTION_BY_REASON: dict[str, str] = {
    "no_validation_panel_for_symbol": "bounded_factor_panels_then_validation_panel_build",
    "no_state_change_join": "run_state_change_for_universe",
    "missing_excess_return_1q": "run_forward_returns_build",
}

JOINED_THRESHOLD_PHASE15 = MIN_SAMPLE_ROWS * 5
THIN_SHARE_MAX_PHASE15 = 0.55
JOINED_THRESHOLD_PHASE16 = MIN_SAMPLE_ROWS * 6
THIN_SHARE_MAX_PHASE16 = 0.45
