"""Phase 35 클로즈아웃 후 Phase 36 단일 권고."""

from __future__ import annotations

from typing import Any

P36_STATE_CHANGE_PIT = "narrow_state_change_pit_alignment_or_rerun_for_signal_before_as_of"
P36_CONTINUE_GAIN = "continue_join_audit_after_substrate_headline_moved"
P36_MATURITY = "calendar_maturity_only_forward_for_remaining_immature_symbols"


def recommend_phase36_after_phase35(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    displacement_hypothesis_supported: bool,
    refresh_out: dict[str, Any],
    matured_schedule: dict[str, Any],
) -> dict[str, Any]:
    j_b = int(before.get("joined_recipe_substrate_row_count") or 0)
    j_a = int(after.get("joined_recipe_substrate_row_count") or 0)
    nsc_b = int(
        (before.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
    )
    nsc_a = int(
        (after.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
    )

    joined_delta = j_a - j_b
    nsc_delta = nsc_b - nsc_a
    rep_rows = int(refresh_out.get("repaired_rows_count_on_synchronized_set") or 0)
    mature_eligible = int(matured_schedule.get("matured_eligible_now_count") or 0)

    if joined_delta > 0 or nsc_delta > 0 or rep_rows > 0:
        return {
            "phase36_recommendation": P36_CONTINUE_GAIN,
            "rationale": "joined 또는 no_state_change_join 헤드라인·동기화 집합에 진전 — 동일 상한으로 잔여 행·게이트 재점검.",
        }

    if displacement_hypothesis_supported and nsc_a > 0:
        return {
            "phase36_recommendation": P36_STATE_CHANGE_PIT,
            "rationale": "동기화 행이 no_state_change_join으로 밀린 가설이 유지됨 — PIT(as_of<=signal) 정합·state_change 런 범위를 좁게 재검토.",
        }

    if mature_eligible > 0:
        return {
            "phase36_recommendation": P36_MATURITY,
            "rationale": "미성숙 심볼 중 일부가 성숙 가능 — would_compute_now 만 forward 재시도.",
        }

    return {
        "phase36_recommendation": P36_MATURITY,
        "rationale": "캘린더 성숙 대기·동일 상한 유지; GIS·개념맵은 샘플 전용.",
    }
