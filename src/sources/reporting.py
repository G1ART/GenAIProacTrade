"""Registry + overlay gap reports (partner / prioritization ready)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

OVERLAY_ROI_RANKED: list[dict[str, Any]] = [
    {
        "rank": 1,
        "overlay_key": "earnings_call_transcripts",
        "why_it_matters": "Narrative vs filing tension; memo/casebook explainability.",
        "expected_product_impact": "Richer memos; better outlier typing.",
        "affected_downstream_layers": [
            "investigation_memos",
            "outlier_casebook",
            "daily_scanner",
        ],
        "minimum_viable_integration_scope": "Read-only normalized chunks + PIT timestamps.",
        "cost_rights_notes": "Commercial license; redistribution limits vary.",
        "credentials_status": "not_available_yet",
    },
    {
        "rank": 2,
        "overlay_key": "analyst_estimates",
        "why_it_matters": "Expectations gap vs realized fundamentals.",
        "expected_product_impact": "Residual diagnostics; spine untouched.",
        "affected_downstream_layers": [
            "factor_market_validation_panels",
            "outlier_casebook",
            "investigation_memos",
        ],
        "minimum_viable_integration_scope": "Consensus + revision id + fiscal alignment.",
        "cost_rights_notes": "Vendor license.",
        "credentials_status": "not_available_yet",
    },
    {
        "rank": 3,
        "overlay_key": "higher_quality_price_or_intraday",
        "why_it_matters": "Signal-date alignment; staleness artifacts.",
        "expected_product_impact": "Forward-return joins; optional scanner.",
        "affected_downstream_layers": [
            "silver_market_prices_daily",
            "forward_returns",
            "scanner",
        ],
        "minimum_viable_integration_scope": "Vendor PIT bars; never overwrite SEC spine.",
        "cost_rights_notes": "Paid data; exchange rules.",
        "credentials_status": "not_available_yet",
    },
    {
        "rank": 4,
        "overlay_key": "options_or_microstructure_overlay",
        "why_it_matters": "Tail/skew; research lane.",
        "expected_product_impact": "Optional experiments.",
        "affected_downstream_layers": ["research_registry"],
        "minimum_viable_integration_scope": "Strict PIT surface snapshots.",
        "cost_rights_notes": "Often expensive.",
        "credentials_status": "not_available_yet",
    },
]


def build_source_registry_report(client: Any) -> dict[str, Any]:
    sources = dbrec.fetch_data_source_registry_all(client)
    overlays = dbrec.fetch_source_overlay_availability_all(client)
    return {
        "source_count": len(sources),
        "sources": sources,
        "overlay_availability": overlays,
        "by_class": _count_by(sources, "source_class"),
        "by_family": _count_by(sources, "data_family"),
    }


def build_overlay_gap_report(client: Any) -> dict[str, Any]:
    overlays = dbrec.fetch_source_overlay_availability_all(client)
    by_key = {str(o["overlay_key"]): o for o in overlays}
    gaps: list[dict[str, Any]] = []
    for item in OVERLAY_ROI_RANKED:
        key = item["overlay_key"]
        row = by_key.get(key, {})
        gaps.append(
            {
                **item,
                "db_availability": row.get("availability", "not_in_db"),
                "linked_source_id": row.get("linked_source_id"),
                "metadata_json": row.get("metadata_json"),
            }
        )
    required_credentials = [
        {
            "overlay": g["overlay_key"],
            "needed": "commercial_api_or_bulk_license",
            "current": g.get("credentials_status", "not_available_yet"),
        }
        for g in OVERLAY_ROI_RANKED
    ]
    layers = sorted({x for g in OVERLAY_ROI_RANKED for x in g["affected_downstream_layers"]})
    return {
        "report_type": "overlay_gap_v1",
        "roi_ranked_overlays": gaps,
        "high_roi_missing_today": [
            g["overlay_key"] for g in gaps if g.get("db_availability") != "available"
        ],
        "required_credentials_summary": required_credentials,
        "product_layers_that_would_change": layers,
        "truth_spine_rule": "public_spine_primary_no_silent_overlay_merge",
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        out[k] = out.get(k, 0) + 1
    return out
