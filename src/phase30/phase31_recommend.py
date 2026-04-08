"""Phase 30 이후 단일 Phase 31 권고."""

from __future__ import annotations

from typing import Any

PHASE31_EXPAND_SEC_INGEST = "continue_bounded_sec_substrate_ingest"
PHASE31_FACTOR_VALIDATION = "continue_factor_and_validation_materialization"
PHASE31_FORWARD = "continue_validation_and_forward_substrate"
PHASE31_PLATEAU = "public_first_plateau_without_quality_unlock"


def recommend_phase31_branch(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    filing_repair: dict[str, Any],
    silver_repair: dict[str, Any],
) -> dict[str, Any]:
    mq_b = int(before.get("missing_quarter_snapshot_for_cik") or 0)
    mq_a = int(after.get("missing_quarter_snapshot_for_cik") or 0)
    mv_b = int(before.get("missing_validation_symbol_count") or 0)
    mv_a = int(after.get("missing_validation_symbol_count") or 0)
    nfi_before = int(
        (before.get("quarter_snapshot_classification_counts") or {}).get(
            "no_filing_index_for_cik", 0
        )
    )
    nfi_after = int(
        (after.get("quarter_snapshot_classification_counts") or {}).get(
            "no_filing_index_for_cik", 0
        )
    )
    fi_repaired = int(filing_repair.get("repaired_now_count") or 0)
    sil_ins = sum(
        int((a.get("materialize_silver") or {}).get("silver_inserted") or 0)
        for a in (silver_repair.get("actions") or [])
        if not a.get("skipped")
    )

    if mq_a < mq_b or mv_a < mv_b:
        if mv_a < mv_b and mq_a <= mq_b:
            return {
                "phase31_recommendation": PHASE31_FORWARD,
                "rationale": "missing_validation_symbol_count 감소 — 잔여 레지스트리·forward 기판.",
            }
        return {
            "phase31_recommendation": PHASE31_FACTOR_VALIDATION,
            "rationale": "분기 스냅샷/기판 갭 축소 — 팩터·검증 물질화 및 좁은 수리 지속.",
        }

    if nfi_after > 0 and (fi_repaired > 0 or sil_ins > 0) and nfi_after < nfi_before:
        return {
            "phase31_recommendation": PHASE31_EXPAND_SEC_INGEST,
            "rationale": "no_filing_index_for_cik 감소 — 동일 상한·감사로 SEC substrate ingest 반복.",
        }

    if nfi_after > 100 or (nfi_after > 0 and nfi_before > 0 and nfi_after >= nfi_before):
        return {
            "phase31_recommendation": PHASE31_EXPAND_SEC_INGEST,
            "rationale": "filing_index 부재가 여전히 지배적 — 상한 있는 메타/팩트 수집 지속.",
        }

    if mq_a > 0:
        return {
            "phase31_recommendation": PHASE31_FACTOR_VALIDATION,
            "rationale": "분기 스냅샷 공백 잔존 — 스냅샷·팩터·검증 좁은 수리.",
        }

    if mv_a > 0:
        return {
            "phase31_recommendation": PHASE31_FORWARD,
            "rationale": "검증 심볼 갭 잔존 — 레지스트리·forward 기판.",
        }

    return {
        "phase31_recommendation": PHASE31_PLATEAU,
        "rationale": "측정 가능한 진전이 제한적 — 플래토·정책 점검.",
    }
