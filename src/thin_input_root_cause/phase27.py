"""Phase 27 next-move classification (exactly one label)."""

from __future__ import annotations

PHASE27_TARGETED_BACKFILL = "targeted_data_backfill_next"
PHASE27_QUALITY_POLICY = "quality_policy_review_needed"
PHASE27_RERUN_15_16 = "rerun_phase15_16_now_open"
PHASE27_PLATEAU = "public_first_plateau_without_quality_unlock"


def classify_phase27_next_move(
    *,
    recommend_rerun_phase15: bool,
    recommend_rerun_phase16: bool,
    primary_blocker_category: str,
    generic_substrate_sprint_likely_wasteful: bool,
    thin_input_share: float | None,
    joined_substrate_rows: int,
) -> dict[str, object]:
    """
    primary_blocker_category: data_absence | join_logic | quality_policy | mixed
    """
    if recommend_rerun_phase15 or recommend_rerun_phase16:
        return {
            "phase27_recommendation": PHASE27_RERUN_15_16,
            "rationale": "rerun 게이트가 열렸다고 판단됨.",
        }

    if primary_blocker_category == "quality_policy" or (
        primary_blocker_category == "mixed" and generic_substrate_sprint_likely_wasteful
    ):
        return {
            "phase27_recommendation": PHASE27_QUALITY_POLICY,
            "rationale": "기판 수리가 델타를 내지 못하고 thin_input 이 주로 사이클 품질 정책 축인 경우.",
        }

    if generic_substrate_sprint_likely_wasteful and joined_substrate_rows > 0:
        return {
            "phase27_recommendation": PHASE27_PLATEAU,
            "rationale": "조인된 행은 있으나 광범위 수리가 무효였고 게이트도 닫혀 있음.",
        }

    if primary_blocker_category in ("data_absence", "join_logic", "mixed"):
        return {
            "phase27_recommendation": PHASE27_TARGETED_BACKFILL,
            "rationale": "남은 블로커가 데이터/조인에 있고 좁은 백필이 레버리지가 될 수 있음.",
        }

    if (thin_input_share or 0) >= 0.99 and joined_substrate_rows > 0:
        return {
            "phase27_recommendation": PHASE27_QUALITY_POLICY,
            "rationale": "thin_input_share≈1 이고 joined>0 이면 정책/사이클 축 재검토 우선.",
        }

    return {
        "phase27_recommendation": PHASE27_PLATEAU,
        "rationale": "기본 폴백: 품질 게이트 없이 공개 우선 플래토 유지.",
    }
