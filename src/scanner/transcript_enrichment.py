"""Optional transcript overlay hints for daily watchlist messaging (non-scoring, PIT-safe)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from db import records as dbrec

_OVERLAY_KEY = "earnings_call_transcripts"


def _parse_iso_to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def effective_transcript_pit_date(row: dict[str, Any]) -> Optional[date]:
    """PIT anchor: available_at → published_at → event_date (all must be ≤ candidate as_of)."""
    for key in ("available_at", "published_at", "event_date"):
        v = row.get(key)
        if v is None:
            continue
        d = _parse_iso_to_date(str(v))
        if d is not None:
            return d
    return None


def select_pit_safe_normalized_transcript(
    rows: list[dict[str, Any]], *, as_of_calendar_date: str
) -> Optional[dict[str, Any]]:
    """
    Latest row whose PIT anchor is on or before as_of_calendar_date.
    Tie-break: newer PIT date, then newer ingested_at.
    """
    as_of = date.fromisoformat(str(as_of_calendar_date).strip()[:10])
    best: Optional[tuple[date, str, dict[str, Any]]] = None
    for row in rows:
        ed = effective_transcript_pit_date(row)
        if ed is None or ed > as_of:
            continue
        ing = str(row.get("ingested_at") or "")
        if best is None:
            best = (ed, ing, row)
            continue
        bed, bing, _ = best
        if ed > bed or (ed == bed and ing > bing):
            best = (ed, ing, row)
    if best is None:
        return None
    return best[2]


def build_transcript_enrichment_for_candidate_context(
    client: Any, *, ticker: str, as_of_calendar_date: str
) -> dict[str, Any]:
    """
    transcript_enrichment_json for daily_watchlist_entries.
    Does not embed full transcript text. Uses PIT-safe row only.
    """
    ado = str(as_of_calendar_date or "").strip()[:10]
    if len(ado) < 10:
        return {
            "provider_binding": "fmp_v3_earning_call_transcript",
            "source_registry_id": "fmp_earning_call_transcripts_poc",
            "ticker": str(ticker or "").upper().strip(),
            "candidate_as_of_date": ado or None,
            "normalized_transcript_row_present": False,
            "transcript_body_injected_into_scores": False,
            "transcript_body_included_in_this_json": False,
            "transcript_context_noted_in_messaging": False,
            "transcript_text_used_for_message_copy": False,
            "reason": "missing_or_invalid_as_of_calendar_date",
        }
    t = ticker.upper().strip()
    rows = dbrec.fetch_normalized_transcripts_for_ticker_recent(
        client, ticker=t, limit=200
    )
    row = select_pit_safe_normalized_transcript(rows, as_of_calendar_date=ado)
    ov_row = dbrec.fetch_source_overlay_availability_by_key(
        client, overlay_key=_OVERLAY_KEY
    )

    base: dict[str, Any] = {
        "provider_binding": "fmp_v3_earning_call_transcript",
        "source_registry_id": "fmp_earning_call_transcripts_poc",
        "ticker": t,
        "candidate_as_of_date": ado,
        "pit_effective_date_used": (
            effective_transcript_pit_date(row).isoformat() if row else None
        ),
        "normalized_transcript_row_present": bool(row),
        "overlay_availability": (ov_row or {}).get("availability"),
        "overlay_last_checked_at": (ov_row or {}).get("last_checked_at"),
        "transcript_body_injected_into_scores": False,
        "transcript_body_included_in_this_json": False,
    }
    if not row:
        base["transcript_context_noted_in_messaging"] = False
        base["transcript_text_used_for_message_copy"] = False
        base["reason"] = "no_pit_safe_normalized_row"
        return base

    nstatus = str(row.get("normalization_status") or "")
    has_text = bool(str(row.get("transcript_text") or "").strip())
    base["normalization_status"] = nstatus
    base["normalized_transcript_id"] = row.get("id")
    base["fiscal_period"] = row.get("fiscal_period")
    base["event_date"] = row.get("event_date")
    base["available_at"] = row.get("available_at")
    base["source_rights_class"] = row.get("source_rights_class")
    base["provenance_json"] = row.get("provenance_json") or {}
    ok_for_copy = nstatus == "ok" and has_text
    base["transcript_text_used_for_message_copy"] = False
    base["transcript_context_noted_in_messaging"] = ok_for_copy
    base["reason"] = (
        "pit_safe_row_ok_for_context_note"
        if ok_for_copy
        else "pit_safe_row_present_but_not_message_ready"
    )
    return base


def optional_why_matters_transcript_clause(enrichment: dict[str, Any]) -> str:
    """Single sentence; empty if no transcript context should be mentioned."""
    if not enrichment.get("transcript_context_noted_in_messaging"):
        return ""
    fp = enrichment.get("fiscal_period") or "unknown_period"
    return (
        f" A PIT-safe normalized FMP earnings call transcript ({fp}) exists on file for qualitative "
        "context only; deterministic ranking is unchanged."
    )


def build_transcript_enrichment_for_ticker(client: Any, *, ticker: str) -> dict[str, Any]:
    """Backward-compatible default: treat as_of = UTC today (prefer explicit candidate date)."""
    today = datetime.now(timezone.utc).date().isoformat()
    return build_transcript_enrichment_for_candidate_context(
        client, ticker=ticker, as_of_calendar_date=today
    )
