"""스테이지 종료 시점 DB 커버리지 체크포인트 (RPC + 보조 집계)."""

from __future__ import annotations

from typing import Any, Optional

from db import records as dbrec


def _paginate_table(
    client: Any, table: str, columns: str, page_size: int = 1000
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + page_size - 1
        r = (
            client.table(table)
            .select(columns)
            .range(start, end)
            .execute()
        )
        batch = r.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def _distinct_cik_from_table(client: Any, table: str) -> int:
    """페이지네이션으로 cik 열 수집 후 distinct (대용량 대비)."""
    seen: set[str] = set()
    for row in _paginate_table(client, table, "cik", page_size=2000):
        ck = str(row.get("cik") or "").strip()
        if ck:
            seen.add(ck)
    return len(seen)


def build_coverage_checkpoint_report(
    client: Any,
    *,
    requested_issuer_target: Optional[int] = None,
    resolved_issuer_count: Optional[int] = None,
    coverage_stage: Optional[str] = None,
) -> dict[str, Any]:
    rpc = dbrec.rpc_backfill_coverage_counts(client) or {}
    filing_d = _distinct_cik_from_table(client, "filing_index")
    out: dict[str, Any] = {
        "coverage_stage": coverage_stage,
        "requested_issuer_target": requested_issuer_target,
        "resolved_issuer_count": resolved_issuer_count,
        "issuer_master_rows": rpc.get("issuer_master_rows"),
        "filing_index_distinct_cik": filing_d,
        "raw_xbrl_facts_distinct_cik": rpc.get("raw_xbrl_facts_distinct_cik"),
        "silver_xbrl_facts_distinct_cik": rpc.get("silver_xbrl_facts_distinct_cik"),
        "issuer_quarter_snapshots_rows": rpc.get("issuer_quarter_snapshots_rows"),
        "issuer_quarter_snapshots_distinct_cik": rpc.get(
            "issuer_quarter_snapshots_distinct_cik"
        ),
        "issuer_quarter_factor_panels_rows": rpc.get(
            "issuer_quarter_factor_panels_rows"
        ),
        "issuer_quarter_factor_panels_distinct_cik": rpc.get(
            "issuer_quarter_factor_panels_distinct_cik"
        ),
        "forward_returns_daily_horizons_rows": rpc.get(
            "forward_returns_daily_horizons_rows"
        ),
        "forward_returns_distinct_cik": rpc.get("forward_returns_distinct_cik"),
        "factor_market_validation_panels_rows": rpc.get(
            "factor_market_validation_panels_rows"
        ),
        "factor_market_validation_panels_distinct_cik": rpc.get(
            "factor_market_validation_panels_distinct_cik"
        ),
        "state_change_candidates_rows": rpc.get("state_change_candidates_rows"),
        "state_change_candidates_distinct_cik": rpc.get(
            "state_change_candidates_distinct_cik"
        ),
    }
    sc_rows = _paginate_table(client, "issuer_state_change_scores", "cik", 2000)
    sc_cik = {str(x.get("cik") or "") for x in sc_rows if x.get("cik")}
    out["issuer_state_change_scores_rows"] = len(sc_rows)
    out["issuer_state_change_scores_distinct_cik"] = len(sc_cik)
    return out
