"""Phase 20 iteration manager & escalation gate."""

from __future__ import annotations

ITERATION_POLICY_VERSION = "1"

SELECTOR_LATEST = "latest"
SELECTOR_LATEST_SUCCESS = "latest-success"
SELECTOR_LATEST_COMPATIBLE = "latest-compatible"
SELECTOR_LATEST_FOR_PROGRAM = "latest-for-program"
SELECTOR_FROM_LATEST_PAIR = "from-latest-pair"
SELECTOR_LATEST_ACTIVE_SERIES = "latest-active-series"

REPAIR_CAMPAIGN_SELECTORS = frozenset(
    {
        SELECTOR_LATEST,
        SELECTOR_LATEST_SUCCESS,
        SELECTOR_LATEST_COMPATIBLE,
        SELECTOR_LATEST_FOR_PROGRAM,
        SELECTOR_FROM_LATEST_PAIR,  # use resolve_repair_campaign_latest_pair(); not a single run id
    }
)

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
