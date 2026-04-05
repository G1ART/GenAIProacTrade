"""Optional transcript overlay hints for daily watchlist messaging (non-scoring)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

_OVERLAY_KEY = "earnings_call_transcripts"


def build_transcript_enrichment_for_ticker(client: Any, *, ticker: str) -> dict[str, Any]:
    """
    transcript_enrichment_json payload for daily_watchlist_entries.
    Does not embed full transcript text (license/size); references normalized row id.
    """
    t = ticker.upper().strip()
    row = dbrec.fetch_latest_normalized_transcript_for_ticker(client, ticker=t)
    ov_row = dbrec.fetch_source_overlay_availability_by_key(client, overlay_key=_OVERLAY_KEY)

    base: dict[str, Any] = {
        "provider_binding": "fmp_v3_earning_call_transcript",
        "source_registry_id": "fmp_earning_call_transcripts_poc",
        "ticker": t,
        "normalized_transcript_row_present": bool(row),
        "overlay_availability": (ov_row or {}).get("availability"),
        "overlay_last_checked_at": (ov_row or {}).get("last_checked_at"),
        "transcript_body_injected_into_scores": False,
        "transcript_body_included_in_this_json": False,
    }
    if not row:
        base["transcript_context_noted_in_messaging"] = False
        base["transcript_text_used_for_message_copy"] = False
        base["reason"] = "no_normalized_row_for_ticker"
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
        "normalized_row_ok_for_context_note"
        if ok_for_copy
        else "normalized_row_present_but_not_message_ready"
    )
    return base


def optional_why_matters_transcript_clause(enrichment: dict[str, Any]) -> str:
    """Single sentence; empty if no transcript context should be mentioned."""
    if not enrichment.get("transcript_context_noted_in_messaging"):
        return ""
    fp = enrichment.get("fiscal_period") or "unknown_period"
    return (
        f" A normalized FMP earnings call transcript ({fp}) exists on file for qualitative "
        "context only; deterministic ranking is unchanged."
    )
