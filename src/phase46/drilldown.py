"""Formal drill-down contract: decision, message, information, research, provenance, closeout."""

from __future__ import annotations

from typing import Any

VALID_LAYERS = frozenset({"decision", "message", "information", "research", "provenance", "closeout"})


def render_drilldown(
    layer: str,
    *,
    founder_read_model: dict[str, Any],
    representative_pitch: dict[str, Any],
    cockpit_state: dict[str, Any],
    phase45_bundle: dict[str, Any],
    phase44_bundle: dict[str, Any],
) -> dict[str, Any]:
    if layer not in VALID_LAYERS:
        raise ValueError(f"unknown drill-down layer: {layer}")

    summaries = representative_pitch.get("layer_summaries") or {}

    if layer == "decision":
        body = summaries.get("decision") or ""
        extra = {
            "authoritative_recommendation": founder_read_model.get("authoritative_recommendation"),
            "current_stance": founder_read_model.get("current_stance"),
        }
    elif layer == "message":
        body = representative_pitch.get("top_level_pitch") or ""
        extra = {"why_this_matters": representative_pitch.get("why_this_matters")}
    elif layer == "information":
        body = summaries.get("information") or ""
        extra = {"what_changed": founder_read_model.get("what_changed"), "what_did_not_change": founder_read_model.get("what_did_not_change")}
    elif layer == "research":
        body = summaries.get("research") or ""
        extra = {
            "material_falsifier_improvement": (phase44_bundle.get("phase44_truthfulness_assessment") or {}).get(
                "material_falsifier_improvement"
            ),
            "claim_narrowing": phase44_bundle.get("claim_narrowing"),
        }
    elif layer == "provenance":
        body = summaries.get("provenance") or ""
        extra = {
            "trace_links": founder_read_model.get("trace_links"),
            "authoritative_phase": founder_read_model.get("authoritative_phase"),
            "superseded_count": len((phase45_bundle.get("authoritative_resolution") or {}).get("superseded_recommendations") or []),
        }
    else:
        body = summaries.get("closeout") or ""
        extra = {
            "future_reopen_protocol": phase45_bundle.get("future_reopen_protocol"),
            "current_closeout_status": phase45_bundle.get("current_closeout_status"),
        }

    return {
        "layer": layer,
        "summary": body,
        "structured": extra,
        "governed": True,
    }
