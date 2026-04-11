"""잔여 no_state_change_join 행을 PIT 실험실·연구 백로그로 명시적 defer."""

from __future__ import annotations

from typing import Any


def build_residual_pit_deferral_summary(residual_gap_report: dict[str, Any]) -> dict[str, Any]:
    rows = list(residual_gap_report.get("rows") or [])
    syms = sorted(
        {str(r.get("symbol") or "").upper().strip() for r in rows if r.get("symbol")}
    )
    return {
        "policy": "no_broad_state_change_rerun",
        "scope": (
            "join_key_mismatch_and_similar_buckets_are_pit_as_of_boundary_cases_not_headline_closure"
        ),
        "deferred_row_count": len(rows),
        "residual_join_bucket_counts": dict(
            residual_gap_report.get("residual_join_bucket_counts") or {}
        ),
        "symbols_deferred": syms,
        "rows": rows,
    }
