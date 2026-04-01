"""
티커 1개 기준 최근 공시 1건의 메타데이터를 SEC에서 가져와 raw/silver에 적재.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


def _bootstrap_edgar_env() -> None:
    """import edgar 전에 캐시 디렉터리를 고정 (홈 디렉터리 권한 이슈 회피)."""
    root = Path(__file__).resolve().parents[2]
    cache = root / ".edgar_cache"
    cache.mkdir(parents=True, exist_ok=True)
    cache_str = str(cache)
    os.environ.setdefault("EDGAR_LOCAL_DATA_DIR", cache_str)
    # edgar.httpclient는 get_edgar_data_directory()가 아니라 core.edgar_data_dir(기본 ~/.edgar)를 쓰므로 맞춤
    import edgar.core as edgar_core

    edgar_core.edgar_data_dir = os.environ.get("EDGAR_LOCAL_DATA_DIR", cache_str)


_bootstrap_edgar_env()

from edgar import Company, set_identity  # noqa: E402

from config import Settings
from db.client import get_supabase_client
from db.records import (
    insert_raw_filing,
    insert_silver_filing,
    raw_filing_exists,
    silver_filing_exists,
)
from models.raw_filing import RawSecFilingRow
from models.silver_filing import SilverSecFilingRow
from sec.normalize import parse_accepted_at, parse_filed_at, raw_payload_to_normalized_summary


def _format_cik(cik: Union[int, str]) -> str:
    return f"{int(cik):010d}"


def _serialize_dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def filing_to_payload(filing: Any, *, ticker_requested: str) -> dict[str, Any]:
    """EntityFiling 등 edgartools 객체에서 JSON-safe payload 생성."""
    accession = str(getattr(filing, "accession_no", "") or getattr(filing, "accession_number", ""))
    cik = _format_cik(getattr(filing, "cik"))
    company_name = str(getattr(filing, "company", "") or "")
    form = str(getattr(filing, "form", "") or "")
    filing_date = str(getattr(filing, "filing_date", "") or "")
    accepted = getattr(filing, "acceptance_datetime", None)
    source_url = str(getattr(filing, "url", "") or "")

    extra: dict[str, Any] = {}
    for key in (
        "primary_document",
        "primary_doc_description",
        "is_xbrl",
        "is_inline_xbrl",
        "file_number",
        "report_date",
    ):
        if hasattr(filing, key):
            try:
                val = getattr(filing, key)
                if val is not None and not callable(val):
                    if isinstance(val, (str, int, float, bool)):
                        extra[key] = val
                    else:
                        extra[key] = str(val)
            except Exception:  # noqa: BLE001 — 메타데이터 best-effort
                continue

    return {
        "source": "edgartools",
        "ticker_requested": ticker_requested.upper().strip(),
        "cik": cik,
        "company_name": company_name,
        "accession_no": accession,
        "form": form,
        "filing_date": filing_date,
        "acceptance_datetime": _serialize_dt(accepted),
        "source_url": source_url or None,
        **extra,
    }


def fetch_latest_filing_metadata(ticker: str, edgar_identity: str) -> dict[str, Any]:
    """
    네트워크 호출: 티커 기준 가장 최근 공시 1건 메타데이터.
    """
    set_identity(edgar_identity)
    company = Company(ticker.upper().strip())
    filings = company.get_filings().head(1)
    if filings.empty:
        raise RuntimeError(f"티커 {ticker!r}에 대한 공시 메타데이터를 찾지 못했습니다.")
    filing = filings[0]
    return filing_to_payload(filing, ticker_requested=ticker)


def run_sample_ingest(
    ticker: str,
    settings: Settings,
    *,
    client: Any = None,
    fetch_fn: Optional[Callable[[], dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    샘플 1건 ingest. client/fetch_fn 주입 시 테스트에서 네트워크/DB 대체 가능.

    Returns:
        요약 dict (raw_inserted, silver_inserted, accession_no, ...)
    """
    ticker = ticker.upper().strip()
    if client is None:
        client = get_supabase_client(settings)

    fetch = fetch_fn or (lambda: fetch_latest_filing_metadata(ticker, settings.edgar_identity))
    payload = fetch()
    payload_json = json.loads(json.dumps(payload, default=str))

    cik = payload_json["cik"]
    accession_no = payload_json["accession_no"]
    company_name = payload_json["company_name"]
    form = payload_json["form"]
    source_url = payload_json.get("source_url")

    filed_at = parse_filed_at(payload_json.get("filing_date"))
    accepted_at = parse_accepted_at(payload_json.get("acceptance_datetime"))

    now = datetime.now(timezone.utc)
    raw_inserted = False
    silver_inserted = False

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
        logger.info("raw_sec_filings skip (이미 존재): %s %s", cik, accession_no)

    revision_no = 1
    summary = raw_payload_to_normalized_summary(payload_json, revision_no=revision_no)

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
            "silver_sec_filings skip (이미 존재): %s %s r=%s",
            cik,
            accession_no,
            revision_no,
        )

    return {
        "ticker": ticker,
        "cik": cik,
        "accession_no": accession_no,
        "raw_inserted": raw_inserted,
        "silver_inserted": silver_inserted,
    }
