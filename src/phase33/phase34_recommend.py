"""Phase 33 클로즈아웃 이후 Phase 34 단일 권고."""

from __future__ import annotations

from typing import Any

PHASE34_FORWARD_PRICE = "continue_forward_and_price_coverage_with_truth_metrics"
PHASE34_STATE_CHANGE = "inspect_no_state_change_join_for_joined_recipe_plateau"
PHASE34_PLATEAU = "plateau_document_external_and_schedule_next_sprint"


def recommend_phase34_after_phase33(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    price_backfill: dict[str, Any],
    forward_retry: dict[str, Any],
    metric_truth_after: dict[str, Any],
) -> dict[str, Any]:
    me_b = int(before.get("missing_excess_return_1q") or 0)
    me_a = int(after.get("missing_excess_return_1q") or 0)
    j_b = int(before.get("joined_recipe_substrate_row_count") or 0)
    j_a = int(after.get("joined_recipe_substrate_row_count") or 0)
    thin_b = float(before.get("thin_input_share") or 0.0)
    thin_a = float(after.get("thin_input_share") or 0.0)

    price_rec = int(price_backfill.get("price_coverage_repaired_now_count") or 0)
    fwd_ok = int((forward_retry.get("forward_build") or {}).get("success_operations") or 0)
    sym_clear = int(
        metric_truth_after.get("symbol_cleared_from_missing_excess_queue_count") or 0
    )

    if me_a < me_b or j_a > j_b or thin_a < thin_b:
        return {
            "phase34_recommendation": PHASE34_FORWARD_PRICE,
            "rationale": "헤드라인 기판 지표가 개선됨 — truth audit 필드와 함께 동일 상한 반복.",
        }

    if price_rec > 0 or fwd_ok > 0:
        return {
            "phase34_recommendation": PHASE34_FORWARD_PRICE,
            "rationale": "가격·forward 재시도에 진전이 있으나 joined/excess 헤드라인은 아직 — 시그널일·창 성숙·추가 심볼 확장을 상한 내에서 계속.",
        }

    if j_a == j_b and int((after.get("exclusion_distribution") or {}).get("no_state_change_join", 0)) > 0:
        return {
            "phase34_recommendation": PHASE34_STATE_CHANGE,
            "rationale": "joined_recipe_substrate_row_count 정체 — no_state_change_join 잔여 시 state_change·PIT 정합 점검.",
        }

    return {
        "phase34_recommendation": PHASE34_PLATEAU,
        "rationale": "Phase 33 상한 내에서 헤드라인 변화 제한 — 외부 가격·API·성숙 창 감사 후 다음 스프린트 설계.",
    }
