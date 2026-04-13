"""Stable JSON shape hints for a future no-code / web UI."""

from __future__ import annotations

from typing import Any


def build_ui_surface_contract() -> dict[str, Any]:
    return {
        "version": 1,
        "asset_list_cards": {
            "description": "Scrollable list of tracked cohort rows or aggregate cohort card",
            "item_fields": [
                "asset_id",
                "symbol",
                "founder_primary_status",
                "headline_snippet",
                "requires_attention_badge",
            ],
        },
        "asset_detail_cards": {
            "description": "Tabs or accordion: decision, message, information, research, closeout",
            "sections": ["decision_card", "message_card", "information_card", "research_provenance_card", "closeout_reopen_card"],
        },
        "representative_agent_pitch": {
            "description": "Read-only pitch panel from bundle.representative_pitch",
            "fields": [
                "top_level_pitch",
                "why_this_matters",
                "what_changed",
                "what_remains_unproven",
                "what_to_watch_next",
            ],
        },
        "drilldown_panels": {
            "description": "Each panel keyed by layer name; content from drilldown.render_drilldown",
            "layers": ["decision", "message", "information", "research", "provenance", "closeout"],
        },
        "alert_feed": {
            "description": "Chronological alert_ledger entries; filter by asset_id, status",
            "source_file": "data/product_surface/alert_ledger_v1.json",
        },
        "decision_ledger_feed": {
            "description": "Chronological decision_trace entries with linked artifacts",
            "source_file": "data/product_surface/decision_trace_ledger_v1.json",
        },
    }
