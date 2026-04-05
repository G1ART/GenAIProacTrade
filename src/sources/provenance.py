"""Overlay awareness for downstream rows — public spine primary; overlays explicit."""

from __future__ import annotations

from typing import Any

DEFAULT_OVERLAY_KEYS = [
    "earnings_call_transcripts",
    "analyst_estimates",
    "higher_quality_price_or_intraday",
    "options_or_microstructure_overlay",
]


def build_overlay_awareness_snapshot(client: Any | None) -> dict[str, Any]:
    """
    Single snapshot attached to casebook / watchlist rows.
    If registry tables are missing (migration not applied), returns explicit fallback.
    """
    fallback: dict[str, Any] = {
        "truth_spine_provenance": "public_deterministic_primary",
        "overlay_available": False,
        "overlay_not_available_yet": list(DEFAULT_OVERLAY_KEYS),
        "overlay_used_sources": [],
        "overlay_confidence_impact": "registry_unreachable_or_migration_pending",
        "rights_fungibility": "non_fungible_by_design",
        "message": "data_source_registry unreadable; treat as overlay_not_available_yet",
    }
    if client is None:
        return fallback
    try:
        from db import records as dbrec

        reg = dbrec.fetch_data_source_registry_all(client)
        ovl = dbrec.fetch_source_overlay_availability_all(client)
    except Exception:
        return fallback

    active_public = [
        str(r["source_id"])
        for r in reg
        if r.get("activation_status") == "active" and r.get("source_class") == "public"
    ]
    missing: list[str] = []
    available: list[str] = []
    for o in ovl:
        key = str(o.get("overlay_key") or "")
        av = str(o.get("availability") or "")
        if av == "not_available_yet":
            missing.append(key)
        elif av == "available":
            available.append(key)
    return {
        "truth_spine_provenance": "public_deterministic_primary",
        "overlay_available": len(available) > 0,
        "overlay_not_available_yet": missing or list(DEFAULT_OVERLAY_KEYS),
        "overlay_used_sources": active_public,
        "overlay_confidence_impact": (
            "no_premium_attached" if not available else "premium_partial_attached"
        ),
        "rights_fungibility": "non_fungible_by_design",
    }


def tag_field_provenance(*, origin: str, source_id: str | None = None) -> dict[str, Any]:
    """Helper for nested JSON: mark origin lane for one field."""
    return {"origin_lane": origin, "source_id": source_id}
