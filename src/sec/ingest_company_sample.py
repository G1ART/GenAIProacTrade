"""
티커 기준 SEC 공시 메타데이터 fetch + 파이프라인(issuer / filing_index / raw / silver).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def _bootstrap_edgar_env() -> None:
    """import edgar 전에 캐시 디렉터리를 고정 (홈 디렉터리 권한 이슈 회피)."""
    root = Path(__file__).resolve().parents[2]
    cache = root / ".edgar_cache"
    cache.mkdir(parents=True, exist_ok=True)
    cache_str = str(cache)
    os.environ.setdefault("EDGAR_LOCAL_DATA_DIR", cache_str)
    import edgar.core as edgar_core

    edgar_core.edgar_data_dir = os.environ.get("EDGAR_LOCAL_DATA_DIR", cache_str)


_bootstrap_edgar_env()

from edgar import Company, set_identity  # noqa: E402

from config import Settings
from db.client import get_supabase_client
from sec.ingest_pipeline import ingest_filing_payload

logger = logging.getLogger(__name__)


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
            except Exception:  # noqa: BLE001
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


def _filings_head_count(filings: Any, limit: int) -> int:
    if filings.empty:
        return 0
    data = getattr(filings, "data", None)
    if data is not None and hasattr(data, "num_rows"):
        return min(int(data.num_rows), limit)
    return limit


def fetch_recent_filings_for_ticker(
    ticker: str,
    edgar_identity: str,
    limit: int,
) -> Tuple[List[dict[str, Any]], Any]:
    """
    네트워크: 최근 공시 limit 건 + Company 객체(issuer 보강용).
    """
    set_identity(edgar_identity)
    company = Company(ticker.upper().strip())
    filings = company.get_filings().head(limit)
    n = _filings_head_count(filings, limit)
    if n == 0:
        return [], company
    out: List[dict[str, Any]] = []
    for i in range(n):
        out.append(filing_to_payload(filings[i], ticker_requested=ticker))
    return out, company


def fetch_latest_filing_metadata(ticker: str, edgar_identity: str) -> dict[str, Any]:
    """네트워크: 티커 기준 가장 최근 공시 1건."""
    rows, _ = fetch_recent_filings_for_ticker(ticker, edgar_identity, 1)
    if not rows:
        raise RuntimeError(f"티커 {ticker!r}에 대한 공시 메타데이터를 찾지 못했습니다.")
    return rows[0]


def run_sample_ingest(
    ticker: str,
    settings: Settings,
    *,
    client: Any = None,
    fetch_fn: Optional[Callable[[], dict[str, Any]]] = None,
    company: Any = None,
) -> dict[str, Any]:
    """
    단일 티커·단일(또는 fetch_fn으로 주입된) payload ingest.
    """
    ticker = ticker.upper().strip()
    if client is None:
        client = get_supabase_client(settings)

    if fetch_fn is not None:
        payload = fetch_fn()
        co = company
    else:
        pl, co = fetch_recent_filings_for_ticker(ticker, settings.edgar_identity, 1)
        if not pl:
            raise RuntimeError(f"티커 {ticker!r}에 대한 공시 메타데이터를 찾지 못했습니다.")
        payload = pl[0]

    payload_json = json.loads(json.dumps(payload, default=str))
    pipe = ingest_filing_payload(client, payload_json, company=co, run_validation_hook=True)

    return {
        "ticker": ticker,
        "cik": pipe["cik"],
        "accession_no": pipe["accession_no"],
        "issuer_upserted": pipe["issuer_upserted"],
        "filing_index_inserted": pipe["filing_index_inserted"],
        "filing_index_updated": pipe["filing_index_updated"],
        "raw_inserted": pipe["raw_inserted"],
        "silver_inserted": pipe["silver_inserted"],
    }
