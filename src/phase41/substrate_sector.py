"""Sector metadata substrate classification (market_metadata_latest sector field)."""

from __future__ import annotations

from typing import Any


def classify_sector_substrate_row(
    *,
    symbol: str,
    metadata_row: dict[str, Any] | None,
) -> dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    if not metadata_row:
        return {
            "classification": "sector_metadata_missing",
            "sector_label": None,
            "industry_label": None,
            "symbol": sym,
        }
    sector = metadata_row.get("sector")
    industry = metadata_row.get("industry")
    sec_s = str(sector).strip() if sector is not None else ""
    ind_s = str(industry).strip() if industry is not None else ""
    if not sec_s:
        return {
            "classification": "sector_metadata_missing",
            "sector_label": None,
            "industry_label": ind_s or None,
            "symbol": sym,
        }
    return {
        "classification": "sector_metadata_available",
        "sector_label": sec_s,
        "industry_label": ind_s or None,
        "symbol": sym,
    }


def summarize_sector_substrate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    c = Counter(str(r.get("classification") or "") for r in rows)
    sectors = [r.get("sector_label") for r in rows if r.get("sector_label")]
    return {
        "row_count": len(rows),
        "by_classification": dict(c),
        "distinct_sector_labels": sorted({str(s) for s in sectors if s}),
    }
