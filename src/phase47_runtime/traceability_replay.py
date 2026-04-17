"""Phase 47c — replay timeline, event grammar, plot grammar, counterfactual scaffold (bundle + ledgers only)."""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase46.alert_ledger import list_alerts
from phase46.decision_trace_ledger import list_decisions

logger = logging.getLogger(__name__)

REPLAY_LINEAGE_REQUIRED_FIELDS: tuple[str, ...] = (
    "registry_entry_id",
    "message_snapshot_id",
)

REPLAY_LINEAGE_OPTIONAL_FIELDS: tuple[str, ...] = (
    "linked_registry_entry_id",
    "linked_artifact_id",
    "replay_lineage_pointer",
    "active_model_family_name",
)

REPLAY_LINEAGE_ALL_FIELDS: tuple[str, ...] = (
    *REPLAY_LINEAGE_REQUIRED_FIELDS,
    *REPLAY_LINEAGE_OPTIONAL_FIELDS,
)

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


def normalize_timeline_event_lineage(event: dict[str, Any]) -> dict[str, Any]:
    """Ensure every timeline event exposes the lineage keys as strings (possibly empty).

    This lets Today/Replay consumers join on fields without key-missing errors and
    gives ``audit_timeline_events_for_lineage`` a uniform shape to inspect.
    """
    for k in REPLAY_LINEAGE_ALL_FIELDS:
        v = event.get(k)
        event[k] = "" if v is None else str(v).strip()
    return event


def missing_required_lineage_fields(event: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for k in REPLAY_LINEAGE_REQUIRED_FIELDS:
        if not str(event.get(k) or "").strip():
            missing.append(k)
    return missing


def audit_timeline_events_for_lineage(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return counts by lineage completeness across the timeline.

    Keys:
      * ``total``
      * ``with_full_required_lineage``  (all required fields present)
      * ``with_any_required_lineage``
      * ``missing_required_by_event_type``
    """
    total = len(events)
    full = 0
    any_ok = 0
    missing_by_type: dict[str, int] = {}
    for e in events:
        missing = missing_required_lineage_fields(e)
        if not missing:
            full += 1
            any_ok += 1
        else:
            if len(missing) < len(REPLAY_LINEAGE_REQUIRED_FIELDS):
                any_ok += 1
            t = str(e.get("event_type") or "unknown")
            missing_by_type[t] = missing_by_type.get(t, 0) + 1
    return {
        "total": total,
        "with_full_required_lineage": full,
        "with_any_required_lineage": any_ok,
        "missing_required_by_event_type": missing_by_type,
    }


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
    require_lineage: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return replay-safe events sorted by time; error string if unparseable anchor.

    When ``require_lineage`` is True (opt-in strict mode), events missing any
    of ``REPLAY_LINEAGE_REQUIRED_FIELDS`` are dropped from the output and
    logged as warnings. Default ``False`` keeps legacy events (migration mode).
    """
    rm = bundle.get("founder_read_model") or {}
    anchor = _parse_ts(str(bundle.get("generated_utc") or ""))
    if anchor is None:
        return [], "invalid_bundle_generated_utc"

    events: list[dict[str, Any]] = []
    dc = _decision_card_from_bundle(bundle)
    primary_asset = str(rm.get("asset_id") or "").strip()
    bundle_registry_entry_id = str(
        (rm.get("registry_entry_id") or bundle.get("registry_entry_id") or "")
    ).strip()
    bundle_message_snapshot_id = str(
        (rm.get("message_snapshot_id") or bundle.get("message_snapshot_id") or "")
    ).strip()
    events.append(
        {
            "event_id": "evt_bundle_authoritative",
            "timestamp_utc": anchor.isoformat(),
            "event_type": "research_event",
            "asset_id": primary_asset,
            "title": "Authoritative bundle snapshot",
            "stance_at_time": str(rm.get("current_stance") or ""),
            "message_summary": _sanitize_replay_text(str(dc.get("body") or rm.get("headline_message") or "")),
            "evidence_summary": _sanitize_replay_text(
                "; ".join(str(x) for x in (rm.get("what_changed") or [])[:3])
            ),
            "founder_note": "",
            "known_then": "Phase 46 bundle fields as of this `generated_utc` — no later ledger entries implied.",
            "later_outcome_link": None,
            "registry_entry_id": bundle_registry_entry_id,
            "message_snapshot_id": bundle_message_snapshot_id,
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
                "asset_id": str(d.get("asset_id") or "").strip(),
                "title": f"Decision: {d.get('decision_type')}",
                "stance_at_time": str(d.get("decision_type") or ""),
                "message_summary": _sanitize_replay_text(str(d.get("linked_message_summary") or "")),
                "evidence_summary": _sanitize_replay_text(str(d.get("linked_authoritative_artifact") or "")),
                "founder_note": _sanitize_replay_text(str(d.get("founder_note") or "")),
                "known_then": "Ledger fields recorded with this decision row only.",
                "later_outcome_link": "outcome_placeholder in ledger may be filled later — not shown as ex-ante known.",
                "replay_lineage_pointer": str(d.get("replay_lineage_pointer") or ""),
                "message_snapshot_id": str(
                    d.get("message_snapshot_id") or bundle_message_snapshot_id or ""
                ),
                "linked_registry_entry_id": str(d.get("linked_registry_entry_id") or ""),
                "linked_artifact_id": str(d.get("linked_artifact_id") or ""),
                "registry_entry_id": str(
                    d.get("registry_entry_id")
                    or d.get("linked_registry_entry_id")
                    or bundle_registry_entry_id
                    or ""
                ),
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
                "asset_id": str(a.get("asset_id") or "").strip(),
                "title": f"Alert: {a.get('alert_class') or 'signal'}",
                "stance_at_time": "",
                "message_summary": _sanitize_replay_text(str(a.get("message_summary") or "")),
                "evidence_summary": str(a.get("triggering_source_artifact") or "")[:400],
                "founder_note": "",
                "known_then": "Alert record as stored; requires attention flag does not imply future path.",
                "later_outcome_link": None,
                "registry_entry_id": str(
                    a.get("registry_entry_id")
                    or a.get("linked_registry_entry_id")
                    or bundle_registry_entry_id
                    or ""
                ),
                "message_snapshot_id": str(
                    a.get("message_snapshot_id") or bundle_message_snapshot_id or ""
                ),
            }
        )

    now = datetime.now(timezone.utc)
    events.append(
        {
            "event_id": "evt_outcome_review_frame",
            "timestamp_utc": now.isoformat(),
            "event_type": "outcome_checkpoint",
            "asset_id": primary_asset,
            "title": "Review frame (present)",
            "stance_at_time": str(rm.get("current_stance") or ""),
            "message_summary": "Ex-post review only — not knowable at prior decision times.",
            "evidence_summary": "",
            "founder_note": "",
            "known_then": "Separates decision quality (past) from outcome viewing (now).",
            "later_outcome_link": None,
            "registry_entry_id": bundle_registry_entry_id,
            "message_snapshot_id": bundle_message_snapshot_id,
        }
    )

    for e in events:
        normalize_timeline_event_lineage(e)

    if require_lineage:
        strict: list[dict[str, Any]] = []
        for e in events:
            missing = missing_required_lineage_fields(e)
            if missing:
                logger.warning(
                    "replay_event_rejected_missing_lineage",
                    extra={
                        "event_id": e.get("event_id"),
                        "event_type": e.get("event_type"),
                        "missing_required": missing,
                    },
                )
                continue
            strict.append(e)
        events = strict

    events.sort(key=lambda e: e["timestamp_utc"])
    return events, None


def _spectrum_review_context_for_asset(
    *,
    repo_root: Path,
    asset_id: str,
    horizon: str,
    lang: str,
    mock_price_tick: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve REPLAY_LINEAGE_JOIN_V1 row + TODAY_REGISTRY_SURFACE_V1 from one Today spectrum build."""
    from phase47_runtime.phase47e_user_locale import normalize_lang
    from phase47_runtime.today_spectrum import _normalize_mock_price_tick, build_today_spectrum_payload

    hz = (horizon or "short").strip().lower().replace("-", "_")
    lg = normalize_lang(lang)
    mt = _normalize_mock_price_tick(mock_price_tick)
    sp = build_today_spectrum_payload(repo_root=repo_root, horizon=hz, lang=lg, mock_price_tick=mt)
    if not sp.get("ok"):
        return None, None
    raw_rs = sp.get("registry_surface_v1")
    registry_surface = raw_rs if isinstance(raw_rs, dict) else None
    aid = (asset_id or "").strip()
    for r in sp.get("rows") or []:
        if not isinstance(r, dict):
            continue
        if str(r.get("asset_id") or "").strip() != aid:
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        fam = str(sp.get("active_model_family") or "")
        join = {
            "contract": "REPLAY_LINEAGE_JOIN_V1",
            "asset_id": aid,
            "horizon": hz,
            "registry_entry_id": str(sp.get("registry_entry_id") or ""),
            "active_model_family_name": fam,
            "replay_lineage_pointer": str(r.get("replay_lineage_pointer") or ""),
            "message_snapshot_id": str(r.get("message_snapshot_id") or ""),
            "linked_registry_entry_id": str(msg.get("linked_registry_entry_id") or ""),
            "linked_artifact_id": str(msg.get("linked_artifact_id") or ""),
        }
        return join, registry_surface
    return None, registry_surface


def _inject_lineage_into_timeline_events(
    events: list[dict[str, Any]],
    join: dict[str, Any],
    registry_surface: dict[str, Any] | None,
) -> None:
    """Attach Today/registry lineage (+ registry surface) to ledger events for the same asset_id (§6.3)."""
    aid = str(join.get("asset_id") or "").strip()
    if not aid:
        return
    rs_ok = isinstance(registry_surface, dict) and registry_surface.get("contract") == "TODAY_REGISTRY_SURFACE_V1"
    for e in events:
        if str(e.get("asset_id") or "").strip() != aid:
            continue
        if str(join.get("active_model_family_name") or "").strip():
            e["active_model_family_name"] = join["active_model_family_name"]
        if str(join.get("replay_lineage_pointer") or "").strip():
            e["replay_lineage_pointer"] = join["replay_lineage_pointer"]
        if str(join.get("message_snapshot_id") or "").strip():
            e["message_snapshot_id"] = join["message_snapshot_id"]
        if str(join.get("linked_registry_entry_id") or "").strip():
            e["linked_registry_entry_id"] = join["linked_registry_entry_id"]
        if str(join.get("linked_artifact_id") or "").strip():
            e["linked_artifact_id"] = join["linked_artifact_id"]
        if str(join.get("registry_entry_id") or "").strip():
            e["registry_entry_id"] = join["registry_entry_id"]
        if rs_ok:
            e["registry_surface_v1"] = registry_surface


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
            mb: dict[str, Any] = {
                "event_id": event_id,
                "timestamp_utc": e.get("timestamp_utc"),
                "event_type": e.get("event_type"),
                "asset_id": str(e.get("asset_id") or "").strip(),
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
            lineage_keys = (
                "replay_lineage_pointer",
                "message_snapshot_id",
                "linked_registry_entry_id",
                "linked_artifact_id",
                "registry_entry_id",
                "active_model_family_name",
            )
            if any(str(e.get(k) or "").strip() for k in lineage_keys):
                for k in lineage_keys:
                    v = e.get(k)
                    if v is not None and str(v).strip():
                        mb[k] = v
            rs = e.get("registry_surface_v1")
            if isinstance(rs, dict) and rs.get("contract") == "TODAY_REGISTRY_SURFACE_V1":
                mb["registry_surface_v1"] = rs
            return mb
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


def build_now_then_frame_v1(
    *,
    bundle: dict[str, Any],
    join: dict[str, Any],
    lang: str | None,
) -> dict[str, Any]:
    """Product Spec §5.3 — connect spectrum-bound 'then' vs authoritative bundle 'now' review frame."""
    from phase47_runtime.phase47e_user_locale import normalize_lang, t

    lg = normalize_lang(lang)
    rm = bundle.get("founder_read_model") or {}
    now_stance = str(rm.get("current_stance") or "")
    now_head = str(rm.get("headline_message") or "")[:220]
    fam = str(join.get("active_model_family_name") or "—")
    snap = str(join.get("message_snapshot_id") or "")
    snap_short = (snap[:56] + "…") if len(snap) > 56 else snap or "—"
    head_short = (now_head[:180] + "…") if len(now_head) > 180 else now_head or "—"
    return {
        "contract": "REPLAY_NOW_THEN_FRAME_V1",
        "then_active_model_family": fam,
        "then_message_snapshot_id": snap,
        "then_replay_lineage_pointer": str(join.get("replay_lineage_pointer") or ""),
        "now_authoritative_bundle_stance": now_stance,
        "now_authoritative_bundle_headline_snippet": now_head,
        "title": t(lg, "replay.now_then.title"),
        "body_then": t(lg, "replay.now_then.body_then").format(family=fam, snapshot_id=snap_short),
        "body_now": t(lg, "replay.now_then.body_now").format(stance=now_stance or "—", headline=head_short),
        "disclaimer": t(lg, "replay.now_then.disclaimer"),
    }


def api_replay_timeline_payload(
    bundle: dict[str, Any],
    alert_path: Path | str,
    decision_path: Path | str,
    *,
    repo_root: Path | None = None,
    timeline_asset_id: str | None = None,
    horizon: str | None = None,
    lang: str | None = None,
    mock_price_tick: str | None = None,
) -> dict[str, Any]:
    ap = Path(alert_path)
    dp = Path(decision_path)
    decisions = list_decisions(dp)
    alerts = list_alerts(ap)
    events, err = build_timeline_events(bundle=bundle, decisions=decisions, alerts=alerts)
    if err:
        return {"ok": False, "error": err, "mode": "replay"}
    join: dict[str, Any] | None = None
    registry_surface: dict[str, Any] | None = None
    if repo_root is not None and (timeline_asset_id or "").strip():
        join, registry_surface = _spectrum_review_context_for_asset(
            repo_root=repo_root,
            asset_id=timeline_asset_id.strip(),
            horizon=horizon or "short",
            lang=lang or "en",
            mock_price_tick=mock_price_tick,
        )
        if join:
            _inject_lineage_into_timeline_events(events, join, registry_surface)
    series = build_plot_series(events, bundle=bundle)
    out: dict[str, Any] = {
        "ok": True,
        "mode": "replay",
        "replay_rules": REPLAY_RULES,
        "replay_lineage_join_contract": "REPLAY_LINEAGE_JOIN_V1",
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
    if join:
        out["today_lineage_join_v1"] = join
        out["now_then_frame_v1"] = build_now_then_frame_v1(bundle=bundle, join=join, lang=lang)
    if isinstance(registry_surface, dict) and registry_surface.get("contract") == "TODAY_REGISTRY_SURFACE_V1":
        out["registry_surface_v1"] = registry_surface
    return out


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
