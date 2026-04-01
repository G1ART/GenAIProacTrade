"""issuer_quarter_snapshots 재생성 배치 + ingest_runs (sec_quarter_snapshot_build)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from config import Settings
from db.client import get_supabase_client
from db.records import ingest_run_create_started, ingest_run_finalize
from sec.facts.facts_pipeline import rebuild_quarter_snapshot_from_db

logger = logging.getLogger(__name__)

RUN_TYPE = "sec_quarter_snapshot_build"


def _distinct_filings_from_silver(client: Any, *, cik: Optional[str], limit: int) -> list[tuple[str, str]]:
    q = client.table("silver_xbrl_facts").select("cik, accession_no")
    if cik:
        q = q.eq("cik", cik)
    r = q.execute()
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in r.data or []:
        key = (row["cik"], row["accession_no"])
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
        if len(pairs) >= limit:
            break
    return pairs


def run_quarter_snapshot_build(
    settings: Settings,
    *,
    client: Any = None,
    ticker: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    silver_xbrl_facts에 있는 (cik, accession)에 대해 스냅샷 upsert.
    ticker가 있으면 issuer_master에서 CIK를 찾아 해당 발행사만.
    """
    if client is None:
        client = get_supabase_client(settings)

    cik_filter: Optional[str] = None
    if ticker:
        im = (
            client.table("issuer_master")
            .select("cik")
            .eq("ticker", ticker.upper().strip())
            .limit(1)
            .execute()
        )
        if not im.data:
            return {
                "run_type": RUN_TYPE,
                "status": "failed",
                "error": "issuer_not_found_for_ticker",
                "ticker": ticker.upper().strip(),
            }
        cik_filter = im.data[0]["cik"]

    pairs = _distinct_filings_from_silver(client, cik=cik_filter, limit=limit)
    meta = {"ticker": ticker, "limit": limit, "filing_pairs": [{"cik": a, "accession_no": b} for a, b in pairs]}
    run_id = ingest_run_create_started(
        client,
        run_type=RUN_TYPE,
        target_count=len(pairs),
        metadata_json=meta,
    )

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for cik, accession_no in pairs:
        try:
            out = rebuild_quarter_snapshot_from_db(client, cik=cik, accession_no=accession_no)
            if out.get("ok"):
                success_count += 1
                results.append(out)
            else:
                failure_count += 1
                errors.append(out)
        except Exception as ex:  # noqa: BLE001
            failure_count += 1
            errors.append({"cik": cik, "accession_no": accession_no, "error": str(ex)})
            logger.exception("snapshot rebuild 실패 %s %s", cik, accession_no)

    status = "completed" if failure_count == 0 else ("completed" if success_count > 0 else "failed")
    ingest_run_finalize(
        client,
        run_id=run_id,
        status=status,
        success_count=success_count,
        failure_count=failure_count,
        error_json={"errors": errors} if errors else None,
    )

    return {
        "run_id": run_id,
        "run_type": RUN_TYPE,
        "status": status,
        "target_count": len(pairs),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
        "errors": errors,
    }
