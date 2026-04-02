"""테이블별 row·distinct CIK 요약 (RPC 우선)."""

from __future__ import annotations

from typing import Any, Optional

from db.records import rpc_backfill_coverage_counts


def build_coverage_report(client: Any) -> dict[str, Any]:
    rpc = rpc_backfill_coverage_counts(client)
    if rpc:
        return {"source": "rpc_backfill_coverage_counts", "counts": rpc}
    return {
        "source": "unavailable",
        "counts": None,
        "hint": "Supabase에 20250408100000_backfill_orchestration.sql RPC 적용 필요",
    }
