"""Phase 28 단일 분기 권고(워크오더 E 질문 6)."""

from __future__ import annotations

from typing import Any

PHASE28_RERUN_15_16 = "rerun_phase15_16_now_open"
PHASE28_CONTINUE_BACKFILL = "continue_targeted_backfill"
PHASE28_QUALITY = "quality_policy_review_needed"
PHASE28_PLATEAU = "public_first_plateau_without_quality_unlock"


def recommend_phase28_branch(
    *,
    recommend_rerun_phase15: bool,
    recommend_rerun_phase16: bool,
    true_repairable_forward: int,
    joined_metadata_flagged: int,
    pit_backfill_candidates: int,
    registry_blocker_total_count: int,
    thin_input_share_after: float | None,
) -> dict[str, Any]:
    if recommend_rerun_phase15 or recommend_rerun_phase16:
        return {
            "phase28_recommendation": PHASE28_RERUN_15_16,
            "rationale": "Phase 15/16 rerun 게이트가 열린 경우 우선.",
        }
    if (
        true_repairable_forward > 0
        or joined_metadata_flagged > 0
        or pit_backfill_candidates > 0
        or registry_blocker_total_count > 0
    ):
        return {
            "phase28_recommendation": PHASE28_CONTINUE_BACKFILL,
            "rationale": "레지스트리·메타·forward·PIT 중 타깃 백필 후보가 남음.",
        }
    if (thin_input_share_after or 0) >= 0.99:
        return {
            "phase28_recommendation": PHASE28_QUALITY,
            "rationale": "타깃 백필 후보도 소진·thin_input_share 가 여전히 높으면 사이클 품질 축 재검토.",
        }
    return {
        "phase28_recommendation": PHASE28_PLATEAU,
        "rationale": "게이트 닫힘·남은 좁은 백필 레버리지가 없으면 공개 우선 플래토 유지.",
    }
