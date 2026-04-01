"""raw/silver 테이블 insert 및 idempotency 조회."""

from __future__ import annotations

from typing import Any

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
