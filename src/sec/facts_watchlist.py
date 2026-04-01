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
from sec.facts.facts_pipeline import run_facts_extract_for_ticker

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_facts_extract"


def run_facts_watchlist(
    settings: Settings,
    *,
    client: Any = None,
    watchlist_path: Optional[Path] = None,
    sleep_seconds: float = 0.65,
    forms: tuple[str, ...] = ("10-Q", "10-K"),
) -> dict[str, Any]:
    tickers, _per = load_watchlist(watchlist_path)
    if client is None:
        client = get_supabase_client(settings)

    meta = {
        "tickers": tickers,
        "watchlist_path": str(watchlist_path or default_watchlist_path()),
        "forms": list(forms),
    }
    run_id = ingest_run_create_started(
        client,
        run_type=RUN_TYPE,
        target_count=len(tickers),
        metadata_json=meta,
    )

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for t in tickers:
        try:
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
        "target_count": len(tickers),
        "success_count": success_count,
        "failure_count": failure_count,
        "tickers": tickers,
        "details": details,
        "errors": errors,
    }
