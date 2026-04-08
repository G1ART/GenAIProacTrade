"""Phase 31 이후 Phase 32 단일 권고."""

from __future__ import annotations

from typing import Any

PHASE32_SILVER_SNAPSHOT = "continue_silver_snapshot_factor_cascade"
PHASE32_RAW_BRIDGE = "continue_raw_xbrl_bridge_bounded"
PHASE32_REGISTRY_FORWARD = "continue_validation_and_forward_substrate"
PHASE32_PLATEAU = "public_first_plateau_without_quality_unlock"


def recommend_phase32_branch(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    raw_repair: dict[str, Any],
    silver_seam: dict[str, Any],
) -> dict[str, Any]:
    mq_b = int(before.get("missing_quarter_snapshot_for_cik") or 0)
    mq_a = int(after.get("missing_quarter_snapshot_for_cik") or 0)
    mv_b = int(before.get("missing_validation_symbol_count") or 0)
    mv_a = int(after.get("missing_validation_symbol_count") or 0)
    nraw_b = int(
        (before.get("quarter_snapshot_classification_counts") or {}).get(
            "filing_index_present_no_raw_facts", 0
        )
    )
    nraw_a = int(
        (after.get("quarter_snapshot_classification_counts") or {}).get(
            "filing_index_present_no_raw_facts", 0
        )
    )
    rsil_b = int(
        (before.get("quarter_snapshot_classification_counts") or {}).get(
            "raw_present_no_silver_facts", 0
        )
    )
    rsil_a = int(
        (after.get("quarter_snapshot_classification_counts") or {}).get(
            "raw_present_no_silver_facts", 0
        )
    )
    raw_ok = int(raw_repair.get("repaired_to_raw_present_count") or 0)
    sil_actions = silver_seam.get("actions") or []
    sil_moved = sum(
        1
        for a in sil_actions
        if str(a.get("classification_before") or "")
        == "raw_present_no_silver_facts"
        and str(a.get("classification_after") or "")
        != "raw_present_no_silver_facts"
    )

    if nraw_a < nraw_b or raw_ok > 0:
        if mq_a < mq_b or mv_a < mv_b:
            return {
                "phase32_recommendation": PHASE32_SILVER_SNAPSHOT,
                "rationale": "raw_xbrl 다리 후 스냅샷/팩터/검증 델타 — 좁은 연쇄 반복.",
            }
        return {
            "phase32_recommendation": PHASE32_RAW_BRIDGE,
            "rationale": "filing_index_present_no_raw_facts 잔존 — 상한 facts extract 지속.",
        }

    if rsil_a < rsil_b or sil_moved > 0:
        return {
            "phase32_recommendation": PHASE32_SILVER_SNAPSHOT,
            "rationale": "silver/스냅샷 경로 개선 — 팩터·검증 물질화.",
        }

    if mv_a > 0 and mv_a < mv_b:
        return {
            "phase32_recommendation": PHASE32_REGISTRY_FORWARD,
            "rationale": "검증 심볼 갭 축소 — 레지스트리·forward 기판.",
        }

    return {
        "phase32_recommendation": PHASE32_PLATEAU,
        "rationale": "측정 가능한 진전 제한 — 플래토 점검.",
    }
