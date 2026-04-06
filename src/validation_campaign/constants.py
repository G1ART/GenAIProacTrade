from __future__ import annotations

from research_validation.constants import (
    BASELINE_NAIVE,
    BASELINE_SIZE,
    BASELINE_STATE_CHANGE,
    CANONICAL_COHORT_DIMENSIONS,
    COHORT_CONFIG_VERSION,
    EXCESS_FIELD,
    HORIZON,
    JOIN_POLICY_VERSION,
    WINDOW_STABILITY_METRIC_KEY,
)

CAMPAIGN_POLICY_VERSION = "1"

JOIN_POLICY_CANONICAL = JOIN_POLICY_VERSION

COHORT_DIMENSIONS = CANONICAL_COHORT_DIMENSIONS

WINDOW_STABILITY_METRIC = WINDOW_STABILITY_METRIC_KEY

RUN_MODES = frozenset({"reuse_only", "reuse_or_run", "force_rerun"})

STRATEGIC_RECOMMENDATIONS = frozenset(
    {
        "public_data_depth_first",
        "targeted_premium_seam_first",
        "insufficient_evidence_repeat_campaign",
    }
)

STRONG_USABLE_QUALITY = frozenset({"strong", "usable_with_gaps"})
THIN_DEGRADED_QUALITY = frozenset(
    {"thin_input", "failed", "degraded", "unknown"}
)


def canonical_baseline_config() -> dict[str, object]:
    return {
        "baselines": [BASELINE_STATE_CHANGE, BASELINE_NAIVE, BASELINE_SIZE],
        "horizon": HORIZON,
        "excess_field": EXCESS_FIELD,
    }
