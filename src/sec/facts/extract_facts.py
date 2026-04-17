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

    하위호환: 내부적으로 ``get_recent_xbrl_filings(..., limit=1)`` 에 위임.
    """
    filings, err = get_recent_xbrl_filings(
        ticker, edgar_identity, forms=forms, limit=1
    )
    if err:
        return None, err
    if not filings:
        return None, {"error": "no_xbrl_filing", "forms": list(forms)}
    return filings[0], None


def get_recent_xbrl_filings(
    ticker: str,
    edgar_identity: str,
    *,
    forms: Tuple[str, ...] = ("10-Q", "10-K"),
    limit: int = 1,
) -> Tuple[List[Any], Optional[dict[str, Any]]]:
    """
    최근 XBRL 공시 최대 ``limit`` 건을 반환한다 (form별 균형 수집).

    **중요 변경**: 과거에는 첫 form(10-Q)에서 limit을 채우면 다른 form(10-K)을 스캔하지 않아
    연간 Q4(FY) 스냅샷이 누락되는 문제가 있었다. 이제는 **각 form에서 동일 limit만큼**
    수집한 뒤 accession 중복을 제거하고, 최신순으로 정렬해 상위 ``limit`` 건을 반환한다.

    - XBRL이 비어있는 공시는 건너뜀.
    - accession 기준 중복 제거.
    - 최종 정렬: filing_date 내림차순 (최신 → 과거), 동률 시 accession_no 내림차순.
    - 충분히 모이지 않아도 수집된 만큼 반환 (에러 아님).

    Returns:
        (filings_list, None) on success (list may be empty)
        (None, {"error": "..."}) on hard failure (e.g. Company not found)
    """
    lim = max(1, int(limit))
    set_identity(edgar_identity)
    try:
        company = Company(ticker.upper().strip())
    except Exception as ex:  # noqa: BLE001
        return [], {"error": "company_lookup_failed", "detail": str(ex)}

    collected_by_form: dict[str, list[Any]] = {}
    seen_accession: set[str] = set()

    for form in forms:
        try:
            filings = company.get_filings(form=form, amendments=False)
        except Exception:  # noqa: BLE001
            continue
        if getattr(filings, "empty", True):
            continue
        try:
            head_n = filings.head(lim)
        except Exception:  # noqa: BLE001
            continue
        form_bucket: list[Any] = []
        for idx in range(lim):
            try:
                f = head_n[idx]
            except Exception:  # noqa: BLE001
                break
            accession = str(
                getattr(f, "accession_no", "") or getattr(f, "accession_number", "") or ""
            )
            if accession and accession in seen_accession:
                continue
            try:
                xbrl = f.xbrl()
            except Exception:  # noqa: BLE001
                continue
            if xbrl is None:
                continue
            if accession:
                seen_accession.add(accession)
            form_bucket.append(f)
        if form_bucket:
            collected_by_form[form] = form_bucket

    def _sort_key(f: Any) -> Tuple[str, str]:
        fd = str(getattr(f, "filing_date", "") or "")
        acc = str(
            getattr(f, "accession_no", "") or getattr(f, "accession_number", "") or ""
        )
        return (fd, acc)

    # 최신순 병합 + 상위 limit건. form별 다양성을 유지하기 위해 병합 후 정렬 방식 사용.
    all_filings: list[Any] = []
    for bucket in collected_by_form.values():
        all_filings.extend(bucket)
    all_filings.sort(key=_sort_key, reverse=True)

    # 최신순 상위 lim건을 기본으로 선택하되, 상위 lim 안에 10-K가 없을 경우
    # 가장 최근 10-K 1건을 강제로 포함시켜 Q4/FY 커버리지를 보장.
    top = all_filings[:lim]
    has_annual = any(
        str(getattr(f, "form", "") or "").upper() in ("10-K", "20-F", "40-F")
        for f in top
    )
    if lim >= 2 and not has_annual:
        for form_name in ("10-K", "20-F", "40-F"):
            bucket = collected_by_form.get(form_name, [])
            if bucket:
                # 가장 최근 10-K 1건을 포함, 가장 오래된 기존 top 1건 대체
                annual = bucket[0]
                top = top[: lim - 1] + [annual]
                top.sort(key=_sort_key, reverse=True)
                break

    return top, None


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


def _extract_one_filing_payload(filing: Any, *, ticker: str) -> dict[str, Any]:
    cik = f"{int(getattr(filing, 'cik')):010d}"
    accession = str(
        getattr(filing, "accession_no", "") or getattr(filing, "accession_number", "")
    )
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
    return _extract_one_filing_payload(filing, ticker=ticker)


def extract_facts_for_ticker_multi(
    ticker: str,
    edgar_identity: str,
    *,
    forms: Tuple[str, ...] = ("10-Q", "10-K"),
    limit: int = 1,
) -> dict[str, Any]:
    """
    단일 티커의 최근 XBRL 공시 최대 ``limit`` 건에 대해 payload 리스트 반환.

    Returns:
        {
          "ok": True,
          "ticker": "NVDA",
          "requested_limit": 5,
          "filings": [ <_extract_one_filing_payload output>, ... ]
        }
        또는 hard failure 시:
        {"ok": False, "error": "...", "ticker": "NVDA", "filings": []}
    """
    tnorm = ticker.upper().strip()
    filings, err = get_recent_xbrl_filings(
        ticker, edgar_identity, forms=forms, limit=limit
    )
    if err:
        return {
            "ok": False,
            "ticker": tnorm,
            "requested_limit": int(limit),
            "filings": [],
            **err,
        }
    if not filings:
        return {
            "ok": False,
            "ticker": tnorm,
            "requested_limit": int(limit),
            "filings": [],
            "error": "no_xbrl_filing",
            "forms": list(forms),
        }

    payloads: list[dict[str, Any]] = []
    for f in filings:
        try:
            payloads.append(_extract_one_filing_payload(f, ticker=tnorm))
        except Exception as ex:  # noqa: BLE001
            payloads.append(
                {
                    "ok": False,
                    "ticker": tnorm,
                    "error": "extract_failed",
                    "detail": str(ex),
                    "accession_no": str(
                        getattr(f, "accession_no", "")
                        or getattr(f, "accession_number", "")
                        or ""
                    ),
                }
            )
    return {
        "ok": any(p.get("ok") for p in payloads),
        "ticker": tnorm,
        "requested_limit": int(limit),
        "filings": payloads,
    }
