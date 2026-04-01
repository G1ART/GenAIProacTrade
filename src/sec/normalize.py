"""
raw payload → silver summary 최소 정규화.

정교한 표준화가 아니라 raw/silver 경계를 고정하는 Phase 0 뼈대.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Optional


def canonical_form_type(form: Optional[str]) -> str:
    """공백 제거, 대문자화, 흔한 슬래시 주변 공백 정리."""
    if not form:
        return ""
    s = str(form).strip().upper()
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_filed_at(value: Optional[str]) -> Optional[datetime]:
    """filing_date 문자열(YYYY-MM-DD 등) → UTC 자정 기준 datetime."""
    if not value:
        return None
    raw = str(value).strip()[:10]
    try:
        d = date.fromisoformat(raw)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_accepted_at(value: Any) -> Optional[datetime]:
    """acceptance_datetime (str | datetime) → timezone-aware UTC 선호."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def raw_payload_to_normalized_summary(
    payload: dict[str, Any],
    *,
    revision_no: int = 1,
) -> dict[str, Any]:
    """
    ingest 단계에서 만든 payload_json을 silver.normalized_summary_json 형태로 변환.
    """
    cik = str(payload.get("cik") or "").strip()
    company_name = str(payload.get("company_name") or "").strip()
    accession = str(payload.get("accession_no") or "").strip()
    raw_form = payload.get("form")

    filed_at = parse_filed_at(payload.get("filing_date"))
    accepted_at = parse_accepted_at(payload.get("acceptance_datetime"))

    canonical = canonical_form_type(raw_form if raw_form is not None else "")

    return {
        "issuer": {
            "cik": cik,
            "company_name": company_name,
        },
        "filing": {
            "accession_no": accession,
            "form_raw": str(raw_form).strip() if raw_form is not None else "",
            "canonical_form": canonical,
        },
        "timestamps": {
            "filed_at": filed_at.isoformat() if filed_at else None,
            "accepted_at": accepted_at.isoformat() if accepted_at else None,
        },
        "revision_no": int(revision_no),
        "normalizer_version": "phase0-v1",
    }
