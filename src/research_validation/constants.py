from __future__ import annotations

HORIZON = "next_quarter"
EXCESS_FIELD = "excess_return_1q"

SURVIVAL_STATUSES = frozenset(
    {"survives", "weak_survival", "demote_to_sandbox", "archive_failed"}
)

MIN_SAMPLE_ROWS = 24
SPREAD_TAIL_FRAC = 0.2
BEAT_BASELINE_EPS = 0.0008
NAIVE_NULL_SPREAD = 0.0
STABILITY_WEAK_THRESHOLD = 0.55
CONTRADICTION_FAIL_THRESHOLD = 2

BASELINE_STATE_CHANGE = "state_change_score_only"
BASELINE_NAIVE = "naive_null"
BASELINE_SIZE = "market_cap_inverse_rank"
