"""Phase 31 `deferred_external_source_gap` facts_extract 예외 행만 상한 재시도."""

from __future__ import annotations

import time
from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import classify_cik_quarter_snapshot_gap
from phase32.phase31_bundle_io import load_phase31_bundle
from sec.facts.facts_pipeline import run_facts_extract_for_ticker


def _classify_retry_outcome(
    *,
    last_exc: str | None,
    extract_ok: bool | None,
    cls_after: str,
) -> str:
    if extract_ok is True:
        if cls_after != "filing_index_present_no_raw_facts":
            return "recovered_on_retry"
        return "persistent_schema_or_mapping_issue"
    if last_exc:
        low = last_exc.lower()
        if any(
            x in low
            for x in (
                "connection",
                "terminated",
                "timeout",
                "temporar",
                "reset",
                "503",
                "502",
            )
        ):
            return "persistent_external_failure"
        return "persistent_external_failure"
    if extract_ok is False:
        return "persistent_schema_or_mapping_issue"
    return "persistent_external_failure"


def retry_raw_facts_deferred_from_phase31_bundle(
    settings: Any,
    *,
    bundle: dict[str, Any] | None = None,
    bundle_path: str | None = None,
    max_rows: int = 20,
    max_attempts_per_row: int = 3,
    initial_backoff_sec: float = 1.5,
) -> dict[str, Any]:
    if bundle is None:
        if not bundle_path:
            raise ValueError("bundle or bundle_path required")
        bundle = load_phase31_bundle(bundle_path)
    raw = bundle.get("raw_facts_backfill_repair") or {}
    deferred = list(
        raw.get("deferred_external_source_gap_all")
        or raw.get("deferred_external_source_gap_sample")
        or []
    )[:max_rows]

    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    results: list[dict[str, Any]] = []
    summary = {
        "recovered_on_retry": 0,
        "persistent_external_failure": 0,
        "persistent_schema_or_mapping_issue": 0,
    }

    for row in deferred:
        reason = str(row.get("reason") or "")
        if reason != "facts_extract_exception":
            continue
        cik = str(row.get("cik") or "").strip()
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip()
        if not ticker and cik:
            t2 = dbrec.fetch_ticker_for_cik(client, cik=cik)
            ticker = str(t2 or "").strip()
        if not ticker:
            bucket = "persistent_schema_or_mapping_issue"
            summary[bucket] += 1
            results.append(
                {
                    "cik": cik,
                    "ticker": ticker,
                    "outcome": bucket,
                    "detail": "no_ticker_for_retry",
                }
            )
            continue

        last_exc: str | None = None
        extract_ok: bool | None = None
        for attempt in range(max_attempts_per_row):
            if attempt:
                time.sleep(initial_backoff_sec * (2 ** (attempt - 1)))
            try:
                ext = run_facts_extract_for_ticker(
                    client,
                    settings,
                    ticker,
                    run_validation_hook=True,
                )
                last_exc = None
                extract_ok = bool(ext.get("ok"))
                if extract_ok:
                    break
            except Exception as ex:  # noqa: BLE001
                last_exc = str(ex)
                extract_ok = None

        cls_after = (
            classify_cik_quarter_snapshot_gap(client, cik=cik) if cik else ""
        )
        outcome = _classify_retry_outcome(
            last_exc=last_exc,
            extract_ok=extract_ok,
            cls_after=cls_after,
        )
        summary[outcome] += 1
        results.append(
            {
                "cik": cik,
                "ticker": ticker,
                "outcome": outcome,
                "classification_after": cls_after,
                "last_error": last_exc,
                "extract_ok_last": extract_ok,
            }
        )

    return {
        "ok": True,
        "repair": "raw_facts_deferred_retry",
        "rows_attempted": len(results),
        "outcome_summary": summary,
        "per_row": results,
    }
