"""report-backfill-status 페이로드 조립."""

from __future__ import annotations

from typing import Any, Optional

from backfill.coverage_report import build_coverage_report
from backfill.join_diagnostics import build_join_diagnostics, thin_factor_issuer_report
from backfill.universe_resolver import resolve_backfill_tickers
from db import records as dbrec


def build_backfill_status_payload(
    client: Any,
    *,
    mode: str,
    universe_name: str,
    symbol_limit: Optional[int] = None,
    include_diagnostics: bool = True,
    thin_threshold: int = 4,
    orchestration_run_id: Optional[str] = None,
) -> dict[str, Any]:
    coverage = build_coverage_report(client)
    tickers, resolve_meta = resolve_backfill_tickers(
        client,
        mode=mode,
        universe_name=universe_name,
        symbol_limit=symbol_limit,
    )
    payload: dict[str, Any] = {
        "mode": mode,
        "universe_name": universe_name,
        "coverage": coverage,
        "resolved_tickers_preview": tickers[:25],
        "resolve_meta": resolve_meta,
    }
    if include_diagnostics:
        payload["join_diagnostics"] = build_join_diagnostics(client, symbols=tickers)
        payload["thin_factor_issuers"] = thin_factor_issuer_report(
            client, threshold=thin_threshold, max_rows=80
        )
        payload["thin_threshold"] = thin_threshold
    if orchestration_run_id:
        orch = dbrec.fetch_backfill_orchestration_run(
            client, run_id=orchestration_run_id
        )
        payload["orchestration_run"] = orch
    else:
        orch = dbrec.fetch_latest_backfill_orchestration(
            client, universe_name=universe_name
        )
        payload["last_orchestration"] = orch
    return payload
