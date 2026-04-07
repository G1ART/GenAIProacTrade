"""Phase 20 iteration manager & escalation gate."""

from __future__ import annotations

ITERATION_POLICY_VERSION = "1"

ESCALATION_RECOMMENDATIONS = frozenset(
    {
        "continue_public_depth",
        "hold_and_repeat_public_repair",
        "open_targeted_premium_discovery",
    }
)

MIN_MEMBERS_FOR_PREMIUM_ESCALATION = 3
JOINED_PLATEAU_MAX_DELTA = 8
THIN_HIGH_THRESHOLD = 0.45
PREMIUM_SHARE_ESCALATION_THRESHOLD = 0.35
JOINED_STRONG_IMPROVEMENT_DELTA = 25
THIN_IMPROVEMENT_MIN_DROP = 0.04
