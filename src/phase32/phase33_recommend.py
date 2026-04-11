"""Phase 32 클로즈아웃 이후 Phase 33 단일 권고."""

from __future__ import annotations

from typing import Any

PHASE33_FORWARD_SUBSTRATE = "continue_bounded_forward_return_and_price_coverage"
PHASE33_PLATEAU = "measure_plateau_reassess_universe_or_state_change"


def recommend_phase33_after_phase32(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    forward_backfill: dict[str, Any],
    silver_snapshot_repair: dict[str, Any],
    raw_deferred_retry: dict[str, Any],
) -> dict[str, Any]:
    me_b = int(before.get("missing_excess_return_1q") or 0)
    me_a = int(after.get("missing_excess_return_1q") or 0)
    j_b = int(before.get("joined_recipe_substrate_row_count") or 0)
    j_a = int(after.get("joined_recipe_substrate_row_count") or 0)
    thin_b = float(before.get("thin_input_share") or 0.0)
    thin_a = float(after.get("thin_input_share") or 0.0)

    fwd_fixed = int(forward_backfill.get("repaired_to_forward_present") or 0)
    raw_rec = int(
        (raw_deferred_retry.get("outcome_summary") or {}).get("recovered_on_retry") or 0
    )
    snap_cleared = int(
        silver_snapshot_repair.get("snapshot_materialized_now_count") or 0
    )

    if me_a < me_b or j_a > j_b or thin_a < thin_b or fwd_fixed > 0:
        return {
            "phase33_recommendation": PHASE33_FORWARD_SUBSTRATE,
            "rationale": "forward/조인 기판이 움직였거나 excess 갭이 줄었음 — 동일 상한으로 forward·가격 창 백필 반복.",
        }

    if raw_rec > 0:
        return {
            "phase33_recommendation": PHASE33_FORWARD_SUBSTRATE,
            "rationale": "raw facts 재시도로 일부 복구 — 하류 연쇄 후 forward 갭 재측정.",
        }

    if snap_cleared > 0:
        return {
            "phase33_recommendation": PHASE33_FORWARD_SUBSTRATE,
            "rationale": "스냅샷 물질화로 팩터·검증이 갱신됨 — forward 백필 재실행.",
        }

    return {
        "phase33_recommendation": PHASE33_PLATEAU,
        "rationale": "Phase 32 상한 수리만으로는 joined/excess가 정체 — 잔여 `missing_excess_return_1q` 행 단위(가격·시그널일) 원인 분석 후 다음 스프린트 설계; `no_filing_index_for_cik` 대량 공략은 우선순위에서 분리.",
    }
