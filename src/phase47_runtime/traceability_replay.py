"""Phase 47c — replay timeline, event grammar, plot grammar, counterfactual scaffold (bundle + ledgers only)."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase46.alert_ledger import list_alerts
from phase46.decision_trace_ledger import list_decisions

EVENT_GRAMMAR: list[dict[str, Any]] = [
    {
        "type": "research_event",
        "label": "Research / bundle",
        "marker": "square",
        "color": "#6b8cce",
        "opacity": 1.0,
        "stroke": "solid",
    },
    {
        "type": "ai_message_event",
        "label": "AI / alert signal",
        "marker": "diamond",
        "color": "#c9a227",
        "opacity": 0.95,
        "stroke": "solid",
    },
    {
        "type": "decision_event",
        "label": "Decision",
        "marker": "circle",
        "color": "#3d9a6e",
        "opacity": 1.0,
        "stroke": "solid",
    },
    {
        "type": "portfolio_event",
        "label": "Portfolio (stub)",
        "marker": "triangle",
        "color": "#a78bfa",
        "opacity": 0.7,
        "stroke": "dashed",
    },
    {
        "type": "market_event",
        "label": "Market reference",
        "marker": "none",
        "color": "#5b8cff",
        "opacity": 0.35,
        "stroke": "dashed",
    },
    {
        "type": "outcome_checkpoint",
        "label": "Outcome frame",
        "marker": "cross",
        "color": "#8b9bb4",
        "opacity": 0.85,
        "stroke": "solid",
    },
]

PLOT_GRAMMAR: dict[str, Any] = {
    "x_axis": "time_utc_iso",
    "series_style_dimensions": ["color", "opacity", "stroke_style", "marker_shape", "band_fill"],
    "default_series": [
        {
            "series_id": "illustrative_reference",
            "role": "market_event",
            "stroke_style": "dashed",
            "opacity": 0.35,
            "disclaimer": "Illustrative only — not live OHLC; shows temporal rhythm for review.",
        },
        {
            "series_id": "stance_posture_index",
            "role": "decision_quality_proxy",
            "stroke_style": "solid",
            "opacity": 0.85,
            "disclaimer": "Ordinal index from stance codes — not a market return.",
        },
    ],
}

REPLAY_RULES: list[str] = [
    "Replay lists only events at or before each point’s timestamp; copy is generated from ledger/bundle fields available for that event.",
    "No counterfactual or hypothetical language in replay event titles or micro-briefs.",
    "Outcome checkpoints labeled as review-time framing, not as if known historically.",
]

COUNTERFACTUAL_RULES: list[str] = [
    "Counterfactual Lab is a separate mode; branches are not drawn as factual timeline markers.",
    "Numeric simulation may be added later; UI grammar reserves branches only.",
    "Copy avoids ‘you would have been rich’ or implied certainty.",
]

DECISION_VS_OUTCOME_RULES: list[str] = [
    "Decision quality: process and evidence fit at decision time.",
    "Outcome quality: ex-post result — may diverge from decision quality.",
    "UI surfaces both labels; does not conflate them.",
]

TRACEABILITY_VIEWS: list[dict[str, str]] = [
    {"id": "replay_timeline", "label": "Replay", "description": "What happened, knowable then, on a time axis."},
    {"id": "counterfactual_lab", "label": "Counterfactual Lab", "description": "Hypothetical branches — not historical replay."},
]

COUNTERFACTUAL_BRANCHES: list[dict[str, str]] = [
    {"id": "actual", "label": "Actual path", "state": "active_in_replay"},
    {"id": "if_not_sold", "label": "If not sold", "state": "stub"},
    {"id": "if_held_longer", "label": "If held longer", "state": "stub"},
    {"id": "if_size_differed", "label": "If size differed", "state": "stub"},
    {"id": "if_watch_only", "label": "If watch-only", "state": "stub"},
    {"id": "if_followed_ai_guidance", "label": "If AI guidance followed", "state": "stub"},
]

_FUTURE_LEAK_PHRASES = (
    "will be",
    "later proved",
    "eventually",
    "in hindsight we know",
    "guaranteed",
)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    t = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def _stance_ordinal(stance: str) -> float:
    s = str(stance or "").lower()
    if "hold" in s:
        return 0.35
    if "watch" in s:
        return 0.55
    if "defer" in s:
        return 0.45
    if "close" in s:
        return 0.25
    return 0.5


def _sanitize_replay_text(text: str, *, max_len: int = 600) -> str:
    t = str(text or "").strip()[:max_len]
    low = t.lower()
    for bad in _FUTURE_LEAK_PHRASES:
        if bad in low:
            t = re.sub(re.escape(bad), "[redacted: hypothetical phrasing]", t, flags=re.IGNORECASE)
    return t


def _decision_card_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    rm = bundle.get("founder_read_model") or {}
    dc = rm.get("decision_card")
    if isinstance(dc, dict) and dc:
        return dc
    agg = (bundle.get("cockpit_state") or {}).get("cohort_aggregate") or {}
    inner = agg.get("decision_card")
    return inner if isinstance(inner, dict) else {}


def build_timeline_events(
    *,
    bundle: dict[str, Any],
    decisions: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Return replay-safe events sorted by time; error string if unparseable anchor."""
    rm = bundle.get("founder_read_model") or {}
    anchor = _parse_ts(str(bundle.get("generated_utc") or ""))
    if anchor is None:
        return [], "invalid_bundle_generated_utc"

    events: list[dict[str, Any]] = []
    dc = _decision_card_from_bundle(bundle)
    events.append(
        {
            "event_id": "evt_bundle_authoritative",
            "timestamp_utc": anchor.isoformat(),
            "event_type": "research_event",
            "title": "Authoritative bundle snapshot",
            "stance_at_time": str(rm.get("current_stance") or ""),
            "message_summary": _sanitize_replay_text(str(dc.get("body") or rm.get("headline_message") or "")),
            "evidence_summary": _sanitize_replay_text(
                "; ".join(str(x) for x in (rm.get("what_changed") or [])[:3])
            ),
            "founder_note": "",
            "known_then": "Phase 46 bundle fields as of this `generated_utc` — no later ledger entries implied.",
            "later_outcome_link": None,
        }
    )

    for i, d in enumerate(decisions):
        ts = _parse_ts(str(d.get("timestamp") or ""))
        if ts is None:
            continue
        events.append(
            {
                "event_id": f"evt_decision_{i}_{d.get('decision_type', 'x')}",
                "timestamp_utc": ts.isoformat(),
                "event_type": "decision_event",
                "title": f"Decision: {d.get('decision_type')}",
                "stance_at_time": str(d.get("decision_type") or ""),
                "message_summary": _sanitize_replay_text(str(d.get("linked_message_summary") or "")),
                "evidence_summary": _sanitize_replay_text(str(d.get("linked_authoritative_artifact") or "")),
                "founder_note": _sanitize_replay_text(str(d.get("founder_note") or "")),
                "known_then": "Ledger fields recorded with this decision row only.",
                "later_outcome_link": "outcome_placeholder in ledger may be filled later — not shown as ex-ante known.",
            }
        )

    for i, a in enumerate(alerts):
        ts = _parse_ts(
            str(a.get("alert_timestamp") or a.get("created_at") or a.get("timestamp") or "")
        )
        if ts is None:
            continue
        events.append(
            {
                "event_id": f"evt_alert_{i}",
                "timestamp_utc": ts.isoformat(),
                "event_type": "ai_message_event",
                "title": f"Alert: {a.get('alert_class') or 'signal'}",
                "stance_at_time": "",
                "message_summary": _sanitize_replay_text(str(a.get("message_summary") or "")),
                "evidence_summary": str(a.get("triggering_source_artifact") or "")[:400],
                "founder_note": "",
                "known_then": "Alert record as stored; requires attention flag does not imply future path.",
                "later_outcome_link": None,
            }
        )

    now = datetime.now(timezone.utc)
    events.append(
        {
            "event_id": "evt_outcome_review_frame",
            "timestamp_utc": now.isoformat(),
            "event_type": "outcome_checkpoint",
            "title": "Review frame (present)",
            "stance_at_time": str(rm.get("current_stance") or ""),
            "message_summary": "Ex-post review only — not knowable at prior decision times.",
            "evidence_summary": "",
            "founder_note": "",
            "known_then": "Separates decision quality (past) from outcome viewing (now).",
            "later_outcome_link": None,
        }
    )

    events.sort(key=lambda e: e["timestamp_utc"])
    return events, None


def build_plot_series(events: list[dict[str, Any]], *, bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Synthetic series for visualization — clearly non-price."""
    rm = bundle.get("founder_read_model") or {}
    if not events:
        return []

    times = [_parse_ts(e["timestamp_utc"]) for e in events]
    times = [t for t in times if t is not None]
    if not times:
        return []
    t0 = min(times)
    t1 = max(times)
    span = (t1 - t0).total_seconds() or 1.0

    ref_points: list[dict[str, Any]] = []
    stance_points: list[dict[str, Any]] = []
    for e in events:
        tt = _parse_ts(e["timestamp_utc"])
        if tt is None:
            continue
        x = (tt - t0).total_seconds() / span
        ref_points.append({"t_iso": e["timestamp_utc"], "x_norm": x, "y": 0.5 + 0.08 * math.sin(x * math.pi)})
        if e["event_type"] == "decision_event":
            stance_points.append(
                {
                    "t_iso": e["timestamp_utc"],
                    "x_norm": x,
                    "y": _stance_ordinal(e.get("stance_at_time", "")),
                }
            )

    return [
        {
            "series_id": "illustrative_reference",
            "role": "market_event",
            "points": ref_points,
            "style": {"stroke": "dashed", "opacity": 0.35, "color": "#5b8cff"},
        },
        {
            "series_id": "stance_posture_index",
            "role": "decision_quality_proxy",
            "points": stance_points or ref_points,
            "style": {"stroke": "solid", "opacity": 0.88, "color": "#3d9a6e"},
        },
    ]


def micro_brief_for_event(events: list[dict[str, Any]], event_id: str) -> dict[str, Any] | None:
    for e in events:
        if e.get("event_id") == event_id:
            g = next((x for x in EVENT_GRAMMAR if x["type"] == e.get("event_type")), {})
            return {
                "event_id": event_id,
                "timestamp_utc": e.get("timestamp_utc"),
                "event_type": e.get("event_type"),
                "style_token": g,
                "title": e.get("title"),
                "stance_at_time": e.get("stance_at_time"),
                "message_summary": e.get("message_summary"),
                "evidence_summary": e.get("evidence_summary"),
                "founder_note": e.get("founder_note"),
                "known_then": e.get("known_then"),
                "decision_quality_note": "Evaluated with information available at this timestamp.",
                "outcome_quality_note": "Outcome quality is assessed separately — may differ from decision quality.",
            }
    return None


def replay_labels_have_no_future_leakage(events: list[dict[str, Any]]) -> bool:
    for e in events:
        if e.get("event_type") == "outcome_checkpoint":
            continue
        blob = " ".join(
            str(e.get(k) or "")
            for k in ("title", "message_summary", "evidence_summary", "known_then")
        ).lower()
        for bad in _FUTURE_LEAK_PHRASES:
            if bad in blob:
                return False
        for bad in ("guaranteed return", "will definitely"):
            if bad in blob:
                return False
    return True


def build_counterfactual_scaffold() -> dict[str, Any]:
    return {
        "mode": "counterfactual_lab",
        "branches": COUNTERFACTUAL_BRANCHES,
        "rules": COUNTERFACTUAL_RULES,
        "disclaimer": "Hypothetical branches — no numeric engine in MVP; not shown on Replay axis.",
    }


def api_replay_timeline_payload(
    bundle: dict[str, Any], alert_path: Path | str, decision_path: Path | str
) -> dict[str, Any]:
    ap = Path(alert_path)
    dp = Path(decision_path)
    decisions = list_decisions(dp)
    alerts = list_alerts(ap)
    events, err = build_timeline_events(bundle=bundle, decisions=decisions, alerts=alerts)
    if err:
        return {"ok": False, "error": err, "mode": "replay"}
    series = build_plot_series(events, bundle=bundle)
    return {
        "ok": True,
        "mode": "replay",
        "replay_rules": REPLAY_RULES,
        "decision_vs_outcome_framing": DECISION_VS_OUTCOME_RULES,
        "event_grammar": EVENT_GRAMMAR,
        "plot_grammar": PLOT_GRAMMAR,
        "events": events,
        "series": series,
        "portfolio_traceability": {
            "state": "stub",
            "note": "Position-level lineage and attribution reserved for a later phase; not implied by this timeline.",
        },
    }


def phase47c_bundle_core(*, design_paths: list[str]) -> dict[str, Any]:
    return {
        "ok": True,
        "phase": "phase47c_traceability_replay",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_source_path": design_paths[0] if design_paths else "",
        "design_sources": design_paths,
        "traceability_views": TRACEABILITY_VIEWS,
        "plot_grammar": PLOT_GRAMMAR,
        "event_grammar": EVENT_GRAMMAR,
        "replay_rules": REPLAY_RULES,
        "counterfactual_rules": COUNTERFACTUAL_RULES,
        "replay_vs_counterfactual_rules": REPLAY_RULES + COUNTERFACTUAL_RULES,
        "decision_quality_vs_outcome_quality_rules": DECISION_VS_OUTCOME_RULES,
        "counterfactual_scaffold": build_counterfactual_scaffold(),
        "phase47d": {
            "phase47d_recommendation": "counterfactual_numeric_engine_and_live_price_attribution_v1",
            "focus": "Numeric simulation for branches, live/benchmark series, attribution wiring — still governance-bound.",
        },
    }
