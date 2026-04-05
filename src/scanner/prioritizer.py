"""Low-noise watchlist prioritization (bounded top-N + score floor)."""

from __future__ import annotations

from typing import Any, Optional

# Documented policy defaults (Phase 8)
DEFAULT_TOP_N = 15
DEFAULT_MIN_PRIORITY_SCORE = 20.0
DEFAULT_MAX_CANDIDATE_RANK = 60

_ALLOWED_CLASSES = frozenset(
    {"investigate_now", "investigate_watch", "recheck_later"}
)


def class_weight(candidate_class: str) -> float:
    return {
        "investigate_now": 45.0,
        "investigate_watch": 28.0,
        "recheck_later": 12.0,
    }.get(candidate_class, 0.0)


def compute_priority_score(
    candidate: dict[str, Any],
    score_row: Optional[dict[str, Any]],
) -> float:
    if not score_row:
        return 0.0
    cc = str(candidate.get("candidate_class") or "")
    rank = int(candidate.get("candidate_rank") or 9999)
    try:
        sc = float(score_row.get("state_change_score_v1") or 0.0)
    except (TypeError, ValueError):
        sc = 0.0
    mag = abs(sc)
    w = class_weight(cc)
    rank_bonus = max(0.0, 80.0 - float(rank)) * 0.35
    return w + mag * 12.0 + rank_bonus


def passes_watchlist_gate(
    candidate: dict[str, Any],
    score_row: Optional[dict[str, Any]],
    *,
    min_priority_score: float,
    max_candidate_rank: int,
) -> bool:
    cc = str(candidate.get("candidate_class") or "")
    if cc not in _ALLOWED_CLASSES:
        return False
    rank = int(candidate.get("candidate_rank") or 9999)
    if rank > max_candidate_rank:
        return False
    pr = compute_priority_score(candidate, score_row)
    return pr >= min_priority_score


def rank_watchlist_candidates(
    pairs: list[tuple[dict[str, Any], Optional[dict[str, Any]]]],
    *,
    top_n: int,
    min_priority_score: float,
    max_candidate_rank: int,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """Returns list of (candidate, score_row, priority) sorted desc, length <= top_n."""
    scored: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for cand, score in pairs:
        if not score:
            continue
        if not passes_watchlist_gate(
            cand,
            score,
            min_priority_score=min_priority_score,
            max_candidate_rank=max_candidate_rank,
        ):
            continue
        p = compute_priority_score(cand, score)
        scored.append((cand, score, p))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[: max(0, int(top_n))]
