"""Phase 17: public substrate depth instrumentation (diagnostics only)."""

from __future__ import annotations

POLICY_VERSION = "phase17_v1"

# PostgREST 단일 응답 한도 내에서 state_change 점수 상한
DEFAULT_STATE_CHANGE_SCORES_LIMIT = 50_000

# 업리프트에 포함할 수치 키(공유 일관성)
UPLIFT_NUMERIC_KEYS = (
    "n_issuer_universe",
    "n_issuer_resolved_cik",
    "n_issuer_with_factor_panel",
    "n_issuer_with_validation_panel_symbol",
    "n_issuer_with_next_quarter_excess",
    "n_issuer_with_state_change_cik",
    "validation_panel_row_count",
    "validation_join_row_count",
    "joined_recipe_substrate_row_count",
)

UPLIFT_SHARE_KEYS = (
    "thin_input_share",
    "degraded_share",
    "strong_share",
    "usable_with_gaps_share",
)

# research-readiness: joined 행이 이 배수 이상이면 Phase 15/16 재실행 권고 완화
READINESS_JOINED_MULTIPLIER = 5
