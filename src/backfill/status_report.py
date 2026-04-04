"""report-backfill-status 페이로드 조립."""

from __future__ import annotations

from typing import Any, Optional

from backfill.checkpoint_report import build_coverage_checkpoint_report
from backfill.coverage_report import build_coverage_report
from backfill.join_diagnostics import build_join_diagnostics, thin_factor_issuer_report
from backfill.sparse_diagnostics import build_sparse_issuer_diagnostics
from backfill.staged_cohort import resolve_staged_coverage_tickers
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
    coverage_stage: Optional[str] = None,
    issuer_target: Optional[int] = None,
    include_coverage_checkpoint: bool = False,
    include_sparse_diagnostics: bool = False,
) -> dict[str, Any]:
    coverage = build_coverage_report(client)
    if coverage_stage:
        tickers, resolve_meta = resolve_staged_coverage_tickers(
            client,
            universe_name=universe_name,
            coverage_stage=coverage_stage,
            issuer_target=issuer_target,
        )
    else:
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
        "coverage_stage": coverage_stage,
        "issuer_target": issuer_target,
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
    if include_coverage_checkpoint:
        payload["coverage_checkpoint"] = build_coverage_checkpoint_report(
            client,
            requested_issuer_target=resolve_meta.get("requested_issuer_target")
            if coverage_stage
            else symbol_limit,
            resolved_issuer_count=len(tickers),
            coverage_stage=coverage_stage,
        )
    if include_sparse_diagnostics:
        payload["sparse_issuer_diagnostics"] = build_sparse_issuer_diagnostics(
            client
        )
    return payload
