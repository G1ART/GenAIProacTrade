"""Supabase 테이블 접근: raw/silver, issuer, filing_index, ingest_runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client


def raw_filing_exists(client: Client, *, cik: str, accession_no: str) -> bool:
    r = (
        client.table("raw_sec_filings")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_raw_filing(client: Client, row: dict[str, Any]) -> None:
    client.table("raw_sec_filings").insert(row).execute()


def silver_filing_exists(
    client: Client, *, cik: str, accession_no: str, revision_no: int
) -> bool:
    r = (
        client.table("silver_sec_filings")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("revision_no", revision_no)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_silver_filing(client: Client, row: dict[str, Any]) -> None:
    client.table("silver_sec_filings").insert(row).execute()


def upsert_issuer_master(client: Client, row: dict[str, Any]) -> None:
    """
    CIK 기준 idempotent upsert. first_seen_at / created_at 은 최초 insert 시만 고정.
    """
    cik = row["cik"]
    now_iso = row["last_seen_at"]
    r = (
        client.table("issuer_master")
        .select("id,first_seen_at,created_at")
        .eq("cik", cik)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd: dict[str, Any] = {
            "company_name": row["company_name"],
            "last_seen_at": now_iso,
            "updated_at": now_iso,
            "is_active": row.get("is_active", True),
        }
        if row.get("ticker"):
            upd["ticker"] = row["ticker"]
        if row.get("sic") is not None:
            upd["sic"] = row["sic"]
        if row.get("sic_description") is not None:
            upd["sic_description"] = row["sic_description"]
        if row.get("latest_known_exchange") is not None:
            upd["latest_known_exchange"] = row["latest_known_exchange"]
        client.table("issuer_master").update(upd).eq("id", oid).execute()
    else:
        client.table("issuer_master").insert(row).execute()


def upsert_filing_index(client: Client, row: dict[str, Any]) -> Dict[str, bool]:
    """
    (cik, accession_no) 유니크. 재실행 시 last_seen_at / 메타 갱신.
    Returns:
        {"inserted": bool, "updated": bool}
    """
    cik = row["cik"]
    acc = row["accession_no"]
    now_iso = row["last_seen_at"]
    r = (
        client.table("filing_index")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", acc)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd = {
            "form": row.get("form"),
            "filed_at": row.get("filed_at"),
            "accepted_at": row.get("accepted_at"),
            "source_url": row.get("source_url"),
            "filing_primary_document": row.get("filing_primary_document"),
            "filing_description": row.get("filing_description"),
            "is_amendment": row.get("is_amendment", False),
            "last_seen_at": now_iso,
            "updated_at": now_iso,
        }
        client.table("filing_index").update(upd).eq("id", oid).execute()
        return {"inserted": False, "updated": True}
    client.table("filing_index").insert(row).execute()
    return {"inserted": True, "updated": False}


def ingest_run_create_started(
    client: Client,
    *,
    run_type: str,
    target_count: Optional[int],
    metadata_json: dict[str, Any],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "run_type": run_type,
        "started_at": now,
        "status": "running",
        "target_count": target_count,
        "success_count": 0,
        "failure_count": 0,
        "metadata_json": metadata_json,
    }
    res = client.table("ingest_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("ingest_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def ingest_run_finalize(
    client: Client,
    *,
    run_id: str,
    status: str,
    success_count: int,
    failure_count: int,
    error_json: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {
        "completed_at": now,
        "status": status,
        "success_count": success_count,
        "failure_count": failure_count,
    }
    if error_json is not None:
        upd["error_json"] = error_json
    client.table("ingest_runs").update(upd).eq("id", run_id).execute()


def smoke_db_select_one(client: Client) -> bool:
    """연결 확인용: issuer_master 0건이어도 성공하면 True."""
    client.table("issuer_master").select("id").limit(1).execute()
    return True
