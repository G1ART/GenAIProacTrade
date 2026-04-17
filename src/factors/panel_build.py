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
    fetch_factor_panel_by_identity,
    fetch_factor_panels_for_cik,
    fetch_issuer_quarter_snapshots_for_cik,
    insert_factor_panel,
    ingest_run_create_started,
    ingest_run_finalize,
    upsert_factor_panel,
)
from factors import DEFAULT_FACTOR_VERSION
from factors.compute_panel import build_factor_panel_row, sort_snapshots_accounting_order

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_factor_panel_build"

_FACTOR_PANEL_SCALAR_KEYS = (
    "accruals",
    "gross_profitability",
    "asset_growth",
    "capex_intensity",
    "rnd_intensity",
    "financial_strength_score",
)


def _factor_panel_needs_refresh(
    existing: dict[str, Any], computed: dict[str, Any]
) -> bool:
    """DB에 NULL로 남은 스칼라 팩터가 재계산으로 채워지면 True."""
    for k in _FACTOR_PANEL_SCALAR_KEYS:
        if existing.get(k) is None and computed.get(k) is not None:
            return True
    return False


def run_factor_panels_for_cik(
    client: Any,
    cik: str,
    *,
    factor_version: str = DEFAULT_FACTOR_VERSION,
    ticker_hint: Optional[str] = None,
    run_id: Optional[str] = None,
    record_run: bool = True,
    refresh_if_stale: bool = True,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    """
    해당 CIK의 모든 분기 스냅샷에 대해 패널 행 생성.

    기본적으로 행이 있어도, DB 팩터 컬럼이 NULL인데 재계산으로 값이 생기면 upsert로 갱신한다
    (스냅샷·실버가 나중에 채워진 뒤에도 패널이 영구 스킵되지 않게).

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
    refreshed_stale = 0
    errors: list[dict[str, Any]] = []

    for snap in ordered:
        try:
            row = build_factor_panel_row(
                snap, ordered, factor_version=factor_version
            )
            fy = int(snap["fiscal_year"])
            fp = str(snap["fiscal_period"])
            acc = str(snap["accession_no"])
            snap_cik = str(snap["cik"])
            exists = factor_panel_exists(
                client,
                cik=snap_cik,
                fiscal_year=fy,
                fiscal_period=fp,
                accession_no=acc,
                factor_version=factor_version,
            )
            if not exists:
                insert_factor_panel(client, row)
                success_count += 1
                continue
            if force_rebuild:
                upsert_factor_panel(client, row)
                refreshed_stale += 1
                success_count += 1
                continue
            if refresh_if_stale:
                existing = fetch_factor_panel_by_identity(
                    client,
                    cik=snap_cik,
                    fiscal_year=fy,
                    fiscal_period=fp,
                    accession_no=acc,
                    factor_version=factor_version,
                )
                if existing and _factor_panel_needs_refresh(existing, row):
                    upsert_factor_panel(client, row)
                    refreshed_stale += 1
                else:
                    skipped_count += 1
                success_count += 1
                continue
            skipped_count += 1
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
        "refreshed_stale": refreshed_stale,
        "errors": errors,
    }


def run_factor_panels_for_ticker(
    settings: Any,
    ticker: str,
    *,
    client: Any | None = None,
    factor_version: str = DEFAULT_FACTOR_VERSION,
    refresh_if_stale: bool = True,
    force_rebuild: bool = False,
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
        refresh_if_stale=refresh_if_stale,
        force_rebuild=force_rebuild,
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
    refresh_if_stale: bool = True,
    force_rebuild: bool = False,
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
            refresh_if_stale=refresh_if_stale,
            force_rebuild=force_rebuild,
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
