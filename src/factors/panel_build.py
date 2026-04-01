"""
DB에서 스냅샷을 읽어 factor panel 적재 + ingest_runs (sec_factor_panel_build).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from db.client import get_supabase_client
from db.records import (
    factor_panel_exists,
    fetch_cik_for_ticker,
    fetch_factor_panels_for_cik,
    fetch_issuer_quarter_snapshots_for_cik,
    insert_factor_panel,
    ingest_run_create_started,
    ingest_run_finalize,
)
from factors import DEFAULT_FACTOR_VERSION
from factors.compute_panel import build_factor_panel_row, sort_snapshots_accounting_order

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_factor_panel_build"


def run_factor_panels_for_cik(
    client: Any,
    cik: str,
    *,
    factor_version: str = DEFAULT_FACTOR_VERSION,
    ticker_hint: Optional[str] = None,
    run_id: Optional[str] = None,
    record_run: bool = True,
) -> dict[str, Any]:
    """
    해당 CIK의 모든 분기 스냅샷에 대해 패널 행 생성(이미 있으면 스킵).
    record_run=False 이면 ingest_runs를 만들지 않고 처리만 (배치에서 상위 run 사용).
    """
    snapshots = fetch_issuer_quarter_snapshots_for_cik(client, cik=cik)
    ordered = sort_snapshots_accounting_order(snapshots)

    created_run = run_id
    if record_run and created_run is None:
        meta = {"cik": cik, "ticker": ticker_hint, "factor_version": factor_version}
        created_run = ingest_run_create_started(
            client,
            run_type=RUN_TYPE,
            target_count=len(ordered),
            metadata_json=meta,
        )

    success_count = 0
    failure_count = 0
    skipped_count = 0
    errors: list[dict[str, Any]] = []

    for snap in ordered:
        try:
            if factor_panel_exists(
                client,
                cik=snap["cik"],
                fiscal_year=int(snap["fiscal_year"]),
                fiscal_period=str(snap["fiscal_period"]),
                accession_no=str(snap["accession_no"]),
                factor_version=factor_version,
            ):
                skipped_count += 1
                success_count += 1
                continue
            row = build_factor_panel_row(
                snap, ordered, factor_version=factor_version
            )
            insert_factor_panel(client, row)
            success_count += 1
        except Exception as ex:  # noqa: BLE001
            failure_count += 1
            errors.append(
                {
                    "cik": cik,
                    "accession_no": snap.get("accession_no"),
                    "error": str(ex),
                }
            )
            logger.exception("factor panel 실패 %s", snap.get("accession_no"))

    status = (
        "failed"
        if failure_count > 0 and success_count == 0
        else ("completed" if failure_count == 0 else "completed")
    )
    if record_run and created_run:
        ingest_run_finalize(
            client,
            run_id=created_run,
            status=status,
            success_count=success_count,
            failure_count=failure_count,
            error_json={"errors": errors} if errors else None,
        )

    return {
        "run_type": RUN_TYPE,
        "run_id": created_run,
        "cik": cik,
        "ticker": ticker_hint,
        "status": status,
        "target_count": len(ordered),
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_existing": skipped_count,
        "errors": errors,
    }


def run_factor_panels_for_ticker(
    settings: Any,
    ticker: str,
    *,
    client: Any | None = None,
    factor_version: str = DEFAULT_FACTOR_VERSION,
) -> dict[str, Any]:
    if client is None:
        client = get_supabase_client(settings)
    t = ticker.upper().strip()
    cik = fetch_cik_for_ticker(client, ticker=t)
    if not cik:
        return {
            "ok": False,
            "error": "issuer_not_found_for_ticker",
            "ticker": t,
        }
    out = run_factor_panels_for_cik(
        client,
        cik,
        factor_version=factor_version,
        ticker_hint=t,
        record_run=True,
    )
    out["ok"] = out.get("failure_count", 0) == 0 or out.get("success_count", 0) > 0
    out["ticker"] = t
    return out


def run_factor_panels_watchlist(
    settings: Any,
    *,
    client: Any | None = None,
    tickers: list[str],
    sleep_seconds: float = 0.65,
    factor_version: str = DEFAULT_FACTOR_VERSION,
) -> dict[str, Any]:
    import time

    if client is None:
        client = get_supabase_client(settings)

    meta = {"tickers": tickers, "factor_version": factor_version}
    run_id = ingest_run_create_started(
        client,
        run_type=RUN_TYPE,
        target_count=len(tickers),
        metadata_json=meta,
    )

    details: list[dict[str, Any]] = []
    agg_errors: list[dict[str, Any]] = []

    for t in tickers:
        cik = fetch_cik_for_ticker(client, ticker=t.upper().strip())
        if not cik:
            agg_errors.append({"ticker": t, "error": "issuer_not_found"})
            time.sleep(sleep_seconds)
            continue
        inner = run_factor_panels_for_cik(
            client,
            cik,
            factor_version=factor_version,
            ticker_hint=t.upper().strip(),
            run_id=None,
            record_run=False,
        )
        inner["ticker"] = t.upper().strip()
        details.append(inner)
        agg_errors.extend(inner.get("errors") or [])
        time.sleep(sleep_seconds)

    row_success = sum(d.get("success_count", 0) for d in details)
    row_fail = sum(d.get("failure_count", 0) for d in details)
    status = "completed" if row_fail == 0 else ("completed" if row_success > 0 else "failed")
    ingest_run_finalize(
        client,
        run_id=run_id,
        status=status,
        success_count=row_success,
        failure_count=row_fail,
        error_json={"errors": agg_errors} if agg_errors else None,
    )

    return {
        "run_id": run_id,
        "run_type": RUN_TYPE,
        "status": status,
        "tickers": tickers,
        "success_count": row_success,
        "failure_count": row_fail,
        "details": details,
        "errors": agg_errors,
    }
