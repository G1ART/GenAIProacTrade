"""Phase 34 클로즈아웃 후 Phase 35 단일 권고."""

from __future__ import annotations

from typing import Any

PHASE35_PROPAGATION = "re_audit_forward_validation_join_and_schedule_matured_windows"
PHASE35_PRICE = "bounded_price_then_forward_for_missing_market_prices_only"
PHASE35_PLATEAU = "document_plateau_external_calendar_and_registry_review"


def recommend_phase35_after_phase34(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    refresh_out: dict[str, Any],
    matured_out: dict[str, Any],
    price_out: dict[str, Any],
    final_gap: dict[str, Any],
) -> dict[str, Any]:
    j_b = int(before.get("joined_recipe_substrate_row_count") or 0)
    j_a = int(after.get("joined_recipe_substrate_row_count") or 0)
    me_b = int(before.get("missing_excess_return_1q") or 0)
    me_a = int(after.get("missing_excess_return_1q") or 0)

    filled = int(refresh_out.get("validation_excess_filled_now_count") or 0)
    sym_b = int(
        refresh_out.get("symbol_cleared_from_missing_excess_queue_count_before") or 0
    )
    sym_a = int(
        refresh_out.get("symbol_cleared_from_missing_excess_queue_count_after") or 0
    )
    sym_delta = sym_a - sym_b

    matured_ok = int(matured_out.get("matured_forward_retry_success_count") or 0)
    price_rec = int(price_out.get("price_coverage_repaired_now_count") or 0)
    not_refreshed = int(
        (final_gap.get("classification_counts") or {}).get(
            "forward_present_validation_not_refreshed", 0
        )
        or 0
    )

    if j_a > j_b or me_a < me_b or filled > 0 or sym_delta > 0 or matured_ok > 0:
        return {
            "phase35_recommendation": PHASE35_PROPAGATION,
            "rationale": "기판 또는 터치 집합 전파·forward에 진전 — 동일 상한으로 재감사 및 성숙 창만 후속 재시도.",
        }

    if price_rec > 0:
        return {
            "phase35_recommendation": PHASE35_PRICE,
            "rationale": "가격 창이 일부 복구됨 — missing_market_prices_daily_window 만 추가 forward 재시도.",
        }

    if not_refreshed > 0:
        return {
            "phase35_recommendation": PHASE35_PROPAGATION,
            "rationale": "forward excess는 있으나 validation excess null 잔여 — 패널 빌드 경로·시그널일 정합 재점검.",
        }

    return {
        "phase35_recommendation": PHASE35_PLATEAU,
        "rationale": "Phase 34 상한 내 헤드라인 변화 제한 — 외부 캘린더·레지스트리·GIS 샘플만 좁게 유지.",
    }
