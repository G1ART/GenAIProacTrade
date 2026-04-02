"""조사 후보 분류 (실행 신호 아님)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CandidateClass = Literal[
    "investigate_now",
    "investigate_watch",
    "recheck_later",
    "insufficient_data",
    "excluded",
]


@dataclass
class IssuerDateScoreRow:
    cik: str
    ticker: str | None
    as_of_date: str
    score: float
    direction: str
    confidence_band: str
    gating_status: str
    missing_component_count: int
    included_component_count: int


def classify_candidate(
    row: IssuerDateScoreRow,
    *,
    rank: int,
    total_ranked: int,
    abs_score_threshold_watch: float = 0.08,
    abs_score_threshold_now: float = 0.15,
) -> tuple[CandidateClass, dict[str, Any], str | None, int]:
    """
    deterministic 규칙: 점수·게이트·순위 기반.
    """
    reason: dict[str, Any] = {
        "rank": rank,
        "state_change_score_v1": row.score,
        "gating_status": row.gating_status,
        "confidence_band": row.confidence_band,
    }
    excluded_reason: str | None = None
    priority = max(0, total_ranked - rank)

    if row.gating_status != "ok":
        return (
            "insufficient_data",
            {**reason, "rule": "gating_not_ok"},
            "gating_" + row.gating_status,
            priority // 2,
        )

    if row.missing_component_count > 6 and row.included_component_count < 2:
        return (
            "insufficient_data",
            {**reason, "rule": "too_many_missing"},
            "missing_components",
            priority // 3,
        )

    a = abs(row.score)
    if a >= abs_score_threshold_now and row.confidence_band != "low":
        return (
            "investigate_now",
            {**reason, "rule": "high_score_and_confidence"},
            None,
            priority + 10,
        )
    if a >= abs_score_threshold_watch:
        return (
            "investigate_watch",
            {**reason, "rule": "moderate_score"},
            None,
            priority + 5,
        )
    if a >= 0.03:
        return (
            "recheck_later",
            {**reason, "rule": "small_signal"},
            None,
            priority,
        )
    return (
        "excluded",
        {**reason, "rule": "below_threshold"},
        "below_score_threshold",
        0,
    )


def dominant_change_type(direction: str) -> str:
    return f"direction_{direction}"
