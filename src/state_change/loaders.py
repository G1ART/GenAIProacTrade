"""
Phase 6 데이터 로더 — 허용 소스만.

금지: factor_market_validation_panels (이 모듈에서 import/조회 없음).
"""

from __future__ import annotations

from typing import Any

from db import records as dbrec


def load_issuers_for_universe_symbols(
    client: Any,
    symbols: list[str],
    *,
    max_issuers: int,
) -> list[dict[str, Any]]:
    """ticker → issuer_master 행 (id, cik, ticker)."""
    rows = dbrec.fetch_issuer_master_rows_for_tickers(client, symbols)
    return rows[: max(0, max_issuers)]


def load_factor_panels_for_cik(
    client: Any,
    *,
    cik: str,
    factor_version: str,
) -> list[dict[str, Any]]:
    return dbrec.fetch_all_factor_panels_for_cik_version(client, cik, factor_version)


def load_snapshots_for_ids(
    client: Any,
    snapshot_ids: list[str],
) -> dict[str, dict[str, Any]]:
    return dbrec.fetch_snapshots_by_ids(client, snapshot_ids)


def load_risk_free_rates_window(
    client: Any,
    *,
    start_date: str,
    end_date: str,
    source_name: str = "fred_dtb3_graph_csv",
) -> list[dict[str, Any]]:
    return dbrec.fetch_risk_free_range(
        client, start_date=start_date, end_date=end_date, source_name=source_name
    )
