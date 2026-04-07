"""Phase 19 repair campaign — bounded decision vocabulary."""

from __future__ import annotations

REPAIR_CAMPAIGN_POLICY_VERSION = "1"

FINAL_DECISIONS = frozenset(
    {
        "continue_public_depth",
        "consider_targeted_premium_seam",
        "repair_insufficient_repeat_buildout",
    }
)

PREMIUM_SHARE_GATE = 0.35
MIN_CONTRADICTORY_FOR_PREMIUM_BRANCH = 1
