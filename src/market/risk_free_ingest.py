"""FRED DTB3 일별 무위험 이자율 적재."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from db.client import get_supabase_client
from db.records import upsert_risk_free_rates_batch, ingest_run_create_started, ingest_run_finalize
from market.risk_free_fred import SOURCE_NAME, fetch_dtb3_series
from market.run_types import RISK_FREE_INGEST

logger = logging.getLogger(__name__)


def run_risk_free_ingest(
    settings: Any,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    lookback_years: int = 3,
    fred_http_timeout_sec: int = 240,
    fred_retries: int = 3,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=365 * lookback_years))
    run_id = ingest_run_create_started(
        client,
        run_type=RISK_FREE_INGEST,
        target_count=None,
        metadata_json={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "source": SOURCE_NAME,
        },
    )
    try:
        rows, dl_err = fetch_dtb3_series(
            start,
            end,
            http_timeout_sec=fred_http_timeout_sec,
            retries=fred_retries,
        )
        if not rows:
            msg = (
                dl_err
                or "다운로드 본문은 있으나 선택 기간에 DTB3 유효 행이 없습니다. --start/--end 를 확인하세요."
            )
            ingest_run_finalize(
                client,
                run_id=run_id,
                status="failed",
                success_count=0,
                failure_count=1,
                error_json={"error": msg, "fred_download_error": dl_err},
            )
            return {
                "status": "failed",
                "rows": 0,
                "source_name": SOURCE_NAME,
                "error": msg,
            }
        logger.info("risk_free_rates_daily Supabase upsert 시작 (%d행, 200행 단위)", len(rows))
        upsert_risk_free_rates_batch(client, rows, chunk_size=200)
        logger.info("risk_free_rates_daily upsert 완료")
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            success_count=len(rows),
            failure_count=0,
            error_json=None,
        )
        return {
            "status": "completed",
            "rows": len(rows),
            "source_name": SOURCE_NAME,
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("risk_free_ingest")
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="failed",
            success_count=0,
            failure_count=1,
            error_json={"error": str(ex)},
        )
        return {"status": "failed", "error": str(ex)}
