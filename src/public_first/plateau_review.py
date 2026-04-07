"""Plateau review conclusions over branch census (Phase 24) — review-only, no premium auto-open."""

from __future__ import annotations

from typing import Any

PUBLIC_FIRST_STILL_IMPROVING = "public_first_still_improving"
MIXED_OR_INSUFFICIENT_EVIDENCE = "mixed_or_insufficient_evidence"
PREMIUM_DISCOVERY_REVIEW_PREPARABLE = "premium_discovery_review_preparable"


def _safe_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0


def conclude_public_first_plateau_review(*, census: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic conclusion from aggregated census (must include active_series_snapshot).

    - premium_discovery_review_preparable: active escalation is open_targeted_premium_discovery
      (human review prep — NOT live integration).
    - public_first_still_improving: enough depth classifications and majority meaningful|marginal.
    - mixed_or_insufficient_evidence: default.
    """
    active = census.get("active_series_snapshot") or {}
    esc = str(active.get("escalation_recommendation_current") or "")

    if esc == "open_targeted_premium_discovery":
        return {
            "ok": True,
            "conclusion": PREMIUM_DISCOVERY_REVIEW_PREPARABLE,
            "reason": "active_series_escalation_is_open_targeted_premium_discovery",
            "premium_live_integration": False,
            "operator_note": (
                "에스컬레이션이 프리미엄 디스커버리 분기입니다. "
                "리뷰·체크리스트 준비만 해당되며 자동 라이브 통합 없음."
            ),
        }

    ded = census.get("deduped_improvement_classification_counts") or {}
    if isinstance(ded, dict) and ded:
        total = sum(_safe_int(v) for v in ded.values())
        mp = _safe_int(ded.get("meaningful_progress"))
        marg = _safe_int(ded.get("marginal_progress"))
    else:
        agg = census.get("aggregated_improvement_classification_counts") or {}
        if not isinstance(agg, dict):
            agg = {}
        total = sum(_safe_int(v) for v in agg.values())
        mp = _safe_int(agg.get("meaningful_progress"))
        marg = _safe_int(agg.get("marginal_progress"))

    if total >= 2 and total > 0 and (mp + marg) / total > 0.5:
        return {
            "ok": True,
            "conclusion": PUBLIC_FIRST_STILL_IMPROVING,
            "reason": "majority_depth_classifications_meaningful_or_marginal",
            "counts": {
                "total_classified_depth_moves": total,
                "meaningful_progress": mp,
                "marginal_progress": marg,
            },
            "premium_live_integration": False,
        }

    return {
        "ok": True,
        "conclusion": MIXED_OR_INSUFFICIENT_EVIDENCE,
        "reason": "insufficient_depth_moves_or_mixed_classification_balance",
        "counts": {
            "total_classified_depth_moves": total,
            "meaningful_progress": mp,
            "marginal_progress": marg,
        },
        "premium_live_integration": False,
    }
