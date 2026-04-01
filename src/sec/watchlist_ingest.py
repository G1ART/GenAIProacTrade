"""워치리스트 기반 다종목 SEC ingest + ingest_runs 감사."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from config import Settings
from watchlist_config import default_watchlist_path, load_watchlist
from db.client import get_supabase_client
from db.records import ingest_run_create_started, ingest_run_finalize
from sec.ingest_company_sample import fetch_recent_filings_for_ticker
from sec.ingest_pipeline import ingest_filing_payload

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_company_watchlist_ingest"


def run_watchlist_ingest(
    settings: Settings,
    *,
    client: Any = None,
    watchlist_path: Optional[Path] = None,
    sleep_seconds: float = 0.65,
) -> dict[str, Any]:
    """
    watchlist.json 의 각 티커에 대해 issuer + filing_index + raw + silver 적재.
    티커 사이 sleep 으로 rate-limit 친화.
    """
    tickers, per_issuer = load_watchlist(watchlist_path)
    if client is None:
        client = get_supabase_client(settings)

    target_filings = len(tickers) * per_issuer
    meta = {
        "tickers": tickers,
        "filings_per_issuer": per_issuer,
        "watchlist_path": str(watchlist_path or default_watchlist_path()),
    }
    run_id = ingest_run_create_started(
        client,
        run_type=RUN_TYPE,
        target_count=target_filings,
        metadata_json=meta,
    )

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []

    for t in tickers:
        try:
            payloads, company = fetch_recent_filings_for_ticker(
                t, settings.edgar_identity, per_issuer
            )
            if not payloads:
                failure_count += 1
                errors.append({"ticker": t, "error": "no_filings"})
                logger.warning("워치리스트 티커 %s: 공시 없음", t)
                time.sleep(sleep_seconds)
                continue
            for payload in payloads:
                try:
                    ingest_filing_payload(
                        client,
                        payload,
                        company=company,
                        run_validation_hook=True,
                    )
                    success_count += 1
                except Exception as ex:  # noqa: BLE001
                    failure_count += 1
                    errors.append(
                        {"ticker": t, "accession_no": payload.get("accession_no"), "error": str(ex)}
                    )
                    logger.exception("filing ingest 실패 %s", t)
        except Exception as ex:  # noqa: BLE001
            failure_count += 1
            errors.append({"ticker": t, "error": str(ex)})
            logger.exception("티커 ingest 실패 %s", t)
        time.sleep(sleep_seconds)

    status = "completed" if success_count > 0 and failure_count == 0 else (
        "completed" if success_count > 0 else "failed"
    )
    err_payload = {"errors": errors} if errors else None
    ingest_run_finalize(
        client,
        run_id=run_id,
        status=status,
        success_count=success_count,
        failure_count=failure_count,
        error_json=err_payload,
    )

    return {
        "run_id": run_id,
        "status": status,
        "target_count": target_filings,
        "success_count": success_count,
        "failure_count": failure_count,
        "tickers": tickers,
    }
