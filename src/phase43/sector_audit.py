"""market_metadata_latest evidence + Phase 42 sector taxonomy."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

from phase42.blocker_taxonomy import classify_sector_blocker_cause


def sector_evidence_snapshot(client: Any, *, symbol: str) -> dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    r = client.table("market_metadata_latest").select("*").eq("symbol", sym).execute()
    raw = [dict(x) for x in (r.data or [])]
    picked = dbrec.fetch_market_metadata_latest_row_deterministic(client, symbol=sym)
    c = classify_sector_blocker_cause(metadata_row=picked)
    sec = (
        str(picked.get("sector") or "").strip()
        if picked and picked.get("sector") is not None
        else ""
    )
    ind = (
        str(picked.get("industry") or "").strip()
        if picked and picked.get("industry") is not None
        else ""
    )
    return {
        "sector_blocker_cause": str(c.get("sector_blocker_cause") or ""),
        "raw_row_count": len(raw),
        "sector_present": bool(sec),
        "industry_present": bool(ind),
    }
