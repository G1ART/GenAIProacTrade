"""
단일 공시 payload에 대한 전체 파이프라인: issuer → filing_index → raw → silver (+ optional 검증 훅).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from db.records import (
    insert_raw_filing,
    insert_silver_filing,
    raw_filing_exists,
    silver_filing_exists,
    upsert_filing_index,
    upsert_issuer_master,
)
from models.raw_filing import RawSecFilingRow
from models.silver_filing import SilverSecFilingRow
from sec.normalize import parse_accepted_at, parse_filed_at, raw_payload_to_normalized_summary
from sec.validation.arelle_check import validate_filing_identity

logger = logging.getLogger(__name__)


def is_amendment_form(form: Optional[str]) -> bool:
    if not form:
        return False
    u = str(form).upper()
    return "/A" in u


def issuer_row_from_payload_and_company(
    payload: dict[str, Any],
    company: Any,
    *,
    now: datetime,
) -> dict[str, Any]:
    cik = payload["cik"]
    ticker = (payload.get("ticker_requested") or "").upper().strip() or None
    company_name = str(payload.get("company_name") or "").strip() or "unknown"
    sic = None
    sic_description = None
    exchange = None
    if company is not None:
        sic = getattr(company, "sic", None)
        if sic is not None:
            sic = str(sic)
        sic_description = getattr(company, "sic_description", None) or getattr(
            company, "industry", None
        )
        if sic_description is not None:
            sic_description = str(sic_description)[:2000]
        exchange = getattr(company, "exchange", None) or getattr(company, "exchanges", None)
        if exchange is not None:
            exchange = str(exchange)[:256]
        ct = getattr(company, "ticker", None)
        if ct and not ticker:
            ticker = str(ct).upper().strip()
    return {
        "cik": cik,
        "ticker": ticker,
        "company_name": company_name,
        "sic": sic,
        "sic_description": sic_description,
        "latest_known_exchange": exchange,
        "is_active": True,
        "first_seen_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def filing_index_row_from_payload(payload: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    form = str(payload.get("form") or "")
    filed_at = parse_filed_at(payload.get("filing_date"))
    accepted_at = parse_accepted_at(payload.get("acceptance_datetime"))
    return {
        "cik": payload["cik"],
        "accession_no": payload["accession_no"],
        "form": form,
        "filed_at": filed_at.isoformat() if filed_at else None,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
        "source_url": payload.get("source_url"),
        "filing_primary_document": payload.get("primary_document"),
        "filing_description": payload.get("primary_doc_description"),
        "is_amendment": is_amendment_form(form),
        "first_seen_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def ingest_filing_payload(
    client: Any,
    payload: dict[str, Any],
    *,
    company: Any = None,
    now: Optional[datetime] = None,
    run_validation_hook: bool = True,
) -> dict[str, Any]:
    """
    issuer_master upsert → filing_index upsert → raw(없을 때만) → silver(rev1 없을 때만).

    Returns:
        플래그 및 식별자 요약 dict
    """
    now = now or datetime.now(timezone.utc)
    payload_json = json.loads(json.dumps(payload, default=str))

    cik = payload_json["cik"]
    accession_no = payload_json["accession_no"]
    company_name = payload_json["company_name"]
    form = payload_json["form"]
    source_url = payload_json.get("source_url")

    issuer_row = issuer_row_from_payload_and_company(payload_json, company, now=now)
    upsert_issuer_master(client, issuer_row)
    issuer_touched = True

    fi_row = filing_index_row_from_payload(payload_json, now=now)
    fi_result = upsert_filing_index(client, fi_row)

    filed_at = parse_filed_at(payload_json.get("filing_date"))
    accepted_at = parse_accepted_at(payload_json.get("acceptance_datetime"))

    raw_inserted = False
    if not raw_filing_exists(client, cik=cik, accession_no=accession_no):
        raw_row = RawSecFilingRow(
            cik=cik,
            company_name=company_name,
            accession_no=accession_no,
            form=form,
            filed_at=filed_at,
            accepted_at=accepted_at,
            source_url=source_url,
            payload_json=payload_json,
            ingested_at=now,
        )
        insert_raw_filing(client, raw_row.to_supabase_dict())
        raw_inserted = True
        logger.info("raw_sec_filings insert: %s %s", cik, accession_no)
    else:
        logger.info("raw_sec_filings skip (immutable, 이미 존재): %s %s", cik, accession_no)

    revision_no = 1
    summary = raw_payload_to_normalized_summary(payload_json, revision_no=revision_no)
    silver_inserted = False
    if not silver_filing_exists(client, cik=cik, accession_no=accession_no, revision_no=revision_no):
        silver_row = SilverSecFilingRow(
            cik=cik,
            company_name=company_name,
            accession_no=accession_no,
            form=summary["filing"]["canonical_form"] or form,
            filed_at=filed_at,
            accepted_at=accepted_at,
            normalized_summary_json=summary,
            revision_no=revision_no,
            created_at=now,
        )
        insert_silver_filing(client, silver_row.to_supabase_dict())
        silver_inserted = True
        logger.info("silver_sec_filings insert: %s %s r=%s", cik, accession_no, revision_no)
    else:
        logger.info(
            "silver_sec_filings skip (rev=%s 이미 존재, 동일 입력 중복 방지): %s %s",
            revision_no,
            cik,
            accession_no,
        )

    validation_result = None
    if run_validation_hook:
        validation_result = validate_filing_identity(payload_json)

    return {
        "cik": cik,
        "accession_no": accession_no,
        "issuer_upserted": issuer_touched,
        "filing_index_inserted": fi_result.get("inserted"),
        "filing_index_updated": fi_result.get("updated"),
        "raw_inserted": raw_inserted,
        "silver_inserted": silver_inserted,
        "arelle_validation": validation_result,
    }
