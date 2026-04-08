"""Phase 29 종료 후 단일 다음 분기 권고."""

from __future__ import annotations

PHASE30_SEC_XBRL_BACKFILL = "continue_sec_xbrl_and_snapshot_pipeline"
PHASE30_VALIDATION_FORWARD = "continue_validation_and_forward_substrate"
PHASE30_QUALITY = "quality_policy_review_needed"
PHASE30_PLATEAU = "public_first_plateau_without_quality_unlock"


def recommend_phase30_branch(
    *,
    joined_metadata_flagged_after: int,
    missing_quarter_snapshot_after: int,
    missing_validation_after: int,
    validation_flags_cleared: int,
    thin_input_share_after: float | None,
    silver_materialization_repair_succeeded: int,
) -> dict[str, Any]:
    if validation_flags_cleared > 0:
        return {
            "phase30_recommendation": PHASE30_VALIDATION_FORWARD,
            "rationale": "검증 패널에서 missing_market_metadata 플래그가 실제로 해소됨 — 잔여 기판·forward 갭 우선.",
        }
    if missing_quarter_snapshot_after > 0:
        return {
            "phase30_recommendation": PHASE30_SEC_XBRL_BACKFILL,
            "rationale": "분기 스냅샷 공백이 남음 — SEC/XBRL·스냅샷 적재 파이프라인(상한·감사 유지).",
        }
    if silver_materialization_repair_succeeded > 0 and missing_validation_after > 0:
        return {
            "phase30_recommendation": PHASE30_VALIDATION_FORWARD,
            "rationale": "스냅샷 일부 복구 후 factor/validation 물질화 재실행.",
        }
    if (thin_input_share_after or 0) >= 0.99 and missing_validation_after == 0:
        return {
            "phase30_recommendation": PHASE30_QUALITY,
            "rationale": "검증 심볼 갭이 없고 thin이 지속되면 사이클 품질 축 점검.",
        }
    if missing_validation_after > 0:
        return {
            "phase30_recommendation": PHASE30_VALIDATION_FORWARD,
            "rationale": "미해결 검증 심볼 잔존 — 레지스트리·패널 타깃 수리 지속.",
        }
    return {
        "phase30_recommendation": PHASE30_PLATEAU,
        "rationale": "좁은 백필 레버가 소진된 플래토 — 공개 우선 유지.",
    }
