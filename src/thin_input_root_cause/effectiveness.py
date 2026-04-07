"""Phase 25 repair path effectiveness / zero-delta audit (Phase 26)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from market.run_types import FACTOR_MARKET_VALIDATION_BUILD, FORWARD_RETURN_BUILD
from public_depth.diagnostics import compute_substrate_coverage
from substrate_closure.diagnose import (
    collect_panels_for_forward_repair,
    collect_panels_for_validation_repair,
)


def _substrate_closure_ingest_runs(client: Any, *, run_type: str, limit: int = 25) -> list[dict[str, Any]]:
    rows = dbrec.fetch_ingest_runs_by_run_types_recent(
        client, run_types=[run_type], limit=limit
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        meta = r.get("metadata_json") if isinstance(r.get("metadata_json"), dict) else {}
        if meta.get("substrate_closure"):
            out.append(
                {
                    "id": r.get("id"),
                    "started_at": r.get("started_at"),
                    "completed_at": r.get("completed_at"),
                    "status": r.get("status"),
                    "success_count": r.get("success_count"),
                    "failure_count": r.get("failure_count"),
                    "target_count": r.get("target_count"),
                    "metadata_json": meta,
                }
            )
    return out


def report_validation_repair_effectiveness(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    panels, meta = collect_panels_for_validation_repair(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    gap = meta.get("diagnosis_summary") or {}
    metrics, excl = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    miss = int(
        excl.get("no_validation_panel_for_symbol", 0)
        if isinstance(excl, dict)
        else 0
    )
    repair_runs = _substrate_closure_ingest_runs(
        client, run_type=FACTOR_MARKET_VALIDATION_BUILD, limit=40
    )
    attempted_ops = sum(int(r.get("success_count") or 0) for r in repair_runs[:5])

    targets = int(meta.get("panel_rows") or len(panels))
    noop = targets == 0
    reasons: list[str] = []
    if noop:
        reasons.append(
            "수리 대상 issuer_quarter 패널이 0건 — "
            "누락 심볼이 validation_panel_build_omission 버킷이 아니면 Phase 25 수리는 적용되지 않음."
        )
    if miss > 0 and targets == 0:
        reasons.append(
            "제외 심볼은 남아 있으나 진단상 빌드 누락 CIK가 없음 → "
            "레지스트리/팩터/티커 정규화 불일치 등 데이터 부재 가능성."
        )

    return {
        "ok": True,
        "repair_path": "validation_panel_coverage",
        "universe_name": universe_name,
        "targets_identified_panel_rows": targets,
        "diagnosis_bucket_counts": gap,
        "current_no_validation_panel_exclusion_rows": miss,
        "recent_substrate_closure_ingest_runs": repair_runs[:8],
        "approx_recent_success_upserts_top5": attempted_ops,
        "likely_no_op": noop,
        "downstream_metrics_note": (
            "substrate exclusion 행은 '심볼당 누락' 집계; "
            "성공 upsert가 있어도 유니버스 심볼 문자열이 canonical 티커와 다르면 카운트가 그대로일 수 있음."
        ),
        "why_unchanged": reasons,
    }


def report_forward_backfill_effectiveness(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    panels, meta = collect_panels_for_forward_repair(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    metrics, excl = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    miss = int(excl.get("missing_excess_return_1q", 0) or 0)
    repair_runs = _substrate_closure_ingest_runs(
        client, run_type=FORWARD_RETURN_BUILD, limit=40
    )
    targets = int(meta.get("panel_rows") or len(panels))
    noop = targets == 0
    reasons: list[str] = []
    if noop:
        reasons.append(
            "no_forward_row_next_quarter 진단 행이 없어 백필 입력 패널이 0건 — "
            "excess 공백이 forward 부재가 아닌 검증 패널 스테일/기타면 Phase 25 forward 수리는 no-op."
        )

    return {
        "ok": True,
        "repair_path": "forward_return_backfill",
        "universe_name": universe_name,
        "targets_identified_panel_rows": targets,
        "forward_gap_counts_snapshot": meta.get("forward_gap_counts"),
        "current_missing_excess_exclusion_rows": miss,
        "recent_substrate_closure_ingest_runs": repair_runs[:8],
        "likely_no_op": noop,
        "why_unchanged": reasons,
    }


def report_state_change_repair_effectiveness(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    metrics_before, excl = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    j_before = int(excl.get("no_state_change_join", 0) or 0)
    sc_runs = dbrec.fetch_state_change_runs_for_universe_recent(
        client, universe_name=universe_name, limit=15
    )
    completed = [r for r in sc_runs if str(r.get("status") or "") == "completed"]

    return {
        "ok": True,
        "repair_path": "state_change_engine",
        "universe_name": universe_name,
        "current_no_state_change_join_exclusion_rows": j_before,
        "latest_completed_state_change_runs": [
            {
                "id": r.get("id"),
                "finished_at": r.get("finished_at"),
                "row_count": r.get("row_count"),
                "warning_count": r.get("warning_count"),
            }
            for r in completed[:5]
        ],
        "note": (
            "Phase 25 state 수리는 엔진 재실행만 수행; "
            "no_state_change_join 이 PIT 간극(시그널 이전 as_of 부재)이면 동일 메트릭이 유지될 수 있음."
        ),
        "likely_no_metric_delta_if": (
            "최신 런이 이미 동일 한계(limit) 내에서 점수를 채웠거나, "
            "조인 실패 행이 시그널·as_of 정렬 문제인 경우."
        ),
        "state_change_run_id_in_metrics": metrics_before.get("state_change_run_id"),
    }
