"""
EdgarTools 기반 XBRL facts 추출 (네트워크).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple

import sec.ingest_company_sample as _ics  # noqa: F401 — edgar 캐시 부트스트랩

from edgar import Company, set_identity

from sec.facts.normalize_facts import dataframe_row_to_raw_fact_dict
from sec.normalize import parse_accepted_at, parse_filed_at


def get_first_xbrl_filing(
    ticker: str,
    edgar_identity: str,
    forms: Tuple[str, ...] = ("10-Q", "10-K"),
) -> Tuple[Any, Optional[dict[str, Any]]]:
    """
    Returns:
        (filing_object, None) on success
        (None, {"error": "..."}) on failure
    """
    set_identity(edgar_identity)
    company = Company(ticker.upper().strip())
    for form in forms:
        filings = company.get_filings(form=form, amendments=False)
        if getattr(filings, "empty", True):
            continue
        try:
            f = filings.head(1)[0]
        except Exception:  # noqa: BLE001
            continue
        xbrl = f.xbrl()
        if xbrl is None:
            continue
        return f, None
    return None, {"error": "no_xbrl_filing", "forms": list(forms)}


def filing_to_metadata_timestamps(filing: Any) -> Tuple[Optional[datetime], Optional[datetime]]:
    fd = str(getattr(filing, "filing_date", "") or "")
    filed_at = parse_filed_at(fd) if fd else None
    accepted = getattr(filing, "acceptance_datetime", None)
    accepted_at = parse_accepted_at(accepted)
    return filed_at, accepted_at


def extract_raw_fact_rows_from_filing(
    filing: Any,
    *,
    cik: str,
    accession_no: str,
) -> List[dict[str, Any]]:
    xbrl = filing.xbrl()
    if xbrl is None:
        return []
    df = xbrl.facts.to_dataframe()
    if df is None or len(df) == 0:
        return []
    filed_at, accepted_at = filing_to_metadata_timestamps(filing)
    rows: List[dict[str, Any]] = []
    for _, series in df.iterrows():
        rows.append(
            dataframe_row_to_raw_fact_dict(
                series,
                cik=cik,
                accession_no=accession_no,
                filed_at=filed_at,
                accepted_at=accepted_at,
            )
        )
    return rows


def extract_facts_for_ticker(
    ticker: str,
    edgar_identity: str,
    *,
    forms: Tuple[str, ...] = ("10-Q", "10-K"),
) -> dict[str, Any]:
    """
    단일 티커에 대해 첫 XBRL 공시에서 raw fact 행 리스트 반환.
    """
    filing, err = get_first_xbrl_filing(ticker, edgar_identity, forms=forms)
    if err:
        return {"ok": False, **err, "ticker": ticker.upper().strip()}
    cik = f"{int(getattr(filing, 'cik')):010d}"
    accession = str(getattr(filing, "accession_no", "") or getattr(filing, "accession_number", ""))
    raw_rows = extract_raw_fact_rows_from_filing(filing, cik=cik, accession_no=accession)
    filed_at, accepted_at = filing_to_metadata_timestamps(filing)
    return {
        "ok": True,
        "ticker": ticker.upper().strip(),
        "cik": cik,
        "accession_no": accession,
        "form": str(getattr(filing, "form", "") or ""),
        "raw_fact_count": len(raw_rows),
        "raw_rows": raw_rows,
        "filed_at": filed_at.isoformat() if filed_at else None,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
    }
