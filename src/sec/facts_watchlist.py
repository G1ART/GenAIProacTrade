"""워치리스트 기반 facts extract + ingest_runs (sec_facts_extract)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from config import Settings
from watchlist_config import default_watchlist_path, load_watchlist
from db.client import get_supabase_client
from db.records import ingest_run_create_started, ingest_run_finalize
from sec.facts.facts_pipeline import (
    run_facts_extract_for_ticker,
    run_facts_extract_for_ticker_multi,
)

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_facts_extract"


def run_facts_extract_for_tickers(
    settings: Settings,
    *,
    tickers: list[str],
    client: Any,
    sleep_seconds: float = 0.65,
    forms: tuple[str, ...] = ("10-Q", "10-K"),
    filings_per_issuer: int = 1,
    metadata_extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    티커 목록에 대해 XBRL facts 추출·적재.

    ``filings_per_issuer`` 가 2 이상이면 티커당 최근 N건의 XBRL 공시를 모두 적재하여
    CIK당 복수 분기 스냅샷을 확보한다 (accruals 등 prior-quarter 의존 팩터 용).
    """
    tnorm = [str(t).upper().strip() for t in tickers if str(t).strip()]
    per = max(1, int(filings_per_issuer))
    meta: dict[str, Any] = {
        "tickers": tnorm,
        "forms": list(forms),
        "filings_per_issuer": per,
        "source": "ticker_list",
    }
    if metadata_extra:
        meta.update(metadata_extra)
    run_id = ingest_run_create_started(
        client,
        run_type=RUN_TYPE,
        target_count=len(tnorm) * per,
        metadata_json=meta,
    )

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for t in tnorm:
        try:
            if per > 1:
                out = run_facts_extract_for_ticker_multi(
                    client,
                    settings,
                    t,
                    limit=per,
                    forms=forms,
                    run_validation_hook=True,
                )
                success_count += int(out.get("filings_ingested") or 0)
                failure_count += int(out.get("filings_failed") or 0)
                inner_errors = out.get("errors") or []
                for er in inner_errors:
                    errors.append({"ticker": t, **er})
                details.append({"ticker": t, "result": out})
            else:
                out = run_facts_extract_for_ticker(
                    client,
                    settings,
                    t,
                    forms=forms,
                    run_validation_hook=True,
                )
                if out.get("ok"):
                    success_count += 1
                    details.append({"ticker": t, "result": out})
                else:
                    failure_count += 1
                    errors.append({"ticker": t, **{k: v for k, v in out.items() if k != "ok"}})
        except Exception as ex:  # noqa: BLE001
            failure_count += 1
            errors.append({"ticker": t, "error": str(ex)})
            logger.exception("facts extract 실패 %s", t)
        time.sleep(sleep_seconds)

    status = (
        "completed"
        if failure_count == 0
        else ("completed" if success_count > 0 else "failed")
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
        "run_type": RUN_TYPE,
        "status": status,
        "target_count": len(tnorm) * per,
        "success_count": success_count,
        "failure_count": failure_count,
        "tickers": tnorm,
        "filings_per_issuer": per,
        "details": details,
        "errors": errors,
    }


def run_facts_watchlist(
    settings: Settings,
    *,
    client: Any = None,
    watchlist_path: Optional[Path] = None,
    sleep_seconds: float = 0.65,
    forms: tuple[str, ...] = ("10-Q", "10-K"),
    filings_per_issuer: Optional[int] = None,
) -> dict[str, Any]:
    """
    watchlist.json 기반 facts extract.

    ``filings_per_issuer`` 가 None이면 watchlist.json의 값을 사용한다.
    명시적으로 지정하면 watchlist.json 값을 override한다.
    """
    tickers, wl_per = load_watchlist(watchlist_path)
    per = int(filings_per_issuer) if filings_per_issuer is not None else int(wl_per)
    if client is None:
        client = get_supabase_client(settings)
    return run_facts_extract_for_tickers(
        settings,
        tickers=tickers,
        client=client,
        sleep_seconds=sleep_seconds,
        forms=forms,
        filings_per_issuer=per,
        metadata_extra={
            "watchlist_path": str(watchlist_path or default_watchlist_path()),
        },
    )
