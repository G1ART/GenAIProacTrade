"""FMP earning_call_transcript JSON → normalized_transcripts row dict."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any, Optional

SOURCE_REGISTRY_ID = "fmp_earning_call_transcripts_poc"
PROVIDER_NAME = "financial_modeling_prep"


def normalize_fmp_earning_call_payload(
    *,
    ticker: str,
    fiscal_year: int,
    fiscal_quarter: int,
    http_status: int,
    payload: Any,
    raw_payload_fmp_id: Optional[str],
    issuer_id: Optional[str],
) -> Optional[dict[str, Any]]:
    """
    Returns row dict for normalized_transcripts insert/upsert, or None if unrecoverable.
    PIT: event_date vs published_at both set from vendor `date` when present (documented limitation).
    """
    if http_status != 200:
        return None
    fiscal_period = f"{fiscal_year}-Q{fiscal_quarter}"
    if not isinstance(payload, list):
        return _row(
            ticker=ticker,
            fiscal_period=fiscal_period,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            event_date=None,
            published_at=None,
            available_at=None,
            text="",
            status="error_unexpected_shape",
            raw_id=raw_payload_fmp_id,
            issuer_id=issuer_id,
            revision_id=None,
        )
    if len(payload) == 0:
        return _row(
            ticker=ticker,
            fiscal_period=fiscal_period,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            event_date=None,
            published_at=None,
            available_at=None,
            text="",
            status="empty_response",
            raw_id=raw_payload_fmp_id,
            issuer_id=issuer_id,
            revision_id=None,
        )
    parts: list[str] = []
    dates: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        c = item.get("content")
        if c:
            parts.append(str(c).strip())
        d = item.get("date")
        if d:
            dates.append(str(d))
    full_text = "\n\n".join(parts) if parts else ""
    primary_date = dates[0] if dates else None
    event_d, pub_ts = _parse_vendor_datetime(primary_date)
    rev = None
    if full_text:
        rev = hashlib.sha256(full_text[:2000].encode()).hexdigest()[:16]
    status = "ok" if full_text else "empty_segments"
    return _row(
        ticker=ticker,
        fiscal_period=fiscal_period,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        event_date=event_d,
        published_at=pub_ts,
        available_at=pub_ts,
        text=full_text,
        status=status,
        raw_id=raw_payload_fmp_id,
        issuer_id=issuer_id,
        revision_id=rev,
    )


def _parse_vendor_datetime(s: Optional[str]) -> tuple[Optional[date], Optional[str]]:
    if not s:
        return None, None
    s = s.strip()
    try:
        if " " in s:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.date(), dt.isoformat()
    except ValueError:
        return None, None


def _row(
    *,
    ticker: str,
    fiscal_period: str,
    fiscal_year: int,
    fiscal_quarter: int,
    event_date: Optional[date],
    published_at: Optional[str],
    available_at: Optional[str],
    text: str,
    status: str,
    raw_id: Optional[str],
    issuer_id: Optional[str],
    revision_id: Optional[str],
) -> dict[str, Any]:
    return {
        "provider_name": PROVIDER_NAME,
        "source_registry_id": SOURCE_REGISTRY_ID,
        "issuer_id": issuer_id,
        "ticker": ticker.strip().upper(),
        "event_date": event_date.isoformat() if event_date else None,
        "fiscal_period": fiscal_period,
        "published_at": published_at,
        "available_at": available_at,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "revision_id": revision_id,
        "transcript_text": text,
        "source_rights_class": "premium",
        "provenance_json": {
            "vendor": PROVIDER_NAME,
            "endpoint_family": "earning_call_transcript_v3",
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "pit_note": (
                "FMP date field treated as vendor publish/time of transcript text; "
                "not assumed same as live call instant."
            ),
            "license_note": "FMP subscription terms apply; redistribution per your FMP plan.",
        },
        "normalization_status": status,
        "raw_payload_fmp_id": raw_id,
    }
