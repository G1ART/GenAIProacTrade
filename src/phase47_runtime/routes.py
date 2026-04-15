"""JSON API handlers for the cockpit runtime (testable without HTTP)."""

from __future__ import annotations

import json
from typing import Any

from phase46.alert_ledger import list_alerts, update_alert_status
from phase46.decision_trace_ledger import DECISION_TYPES, append_decision, list_decisions

from phase47_runtime.governed_conversation import process_governed_prompt
from phase47_runtime.notification_hooks import emit_notification, list_notifications
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.traceability_replay import (
    TRACEABILITY_VIEWS,
    api_replay_timeline_payload,
    build_counterfactual_scaffold,
    micro_brief_for_event,
)
from phase47_runtime.home_feed import build_home_feed_payload
from phase47_runtime.phase47e_user_locale import export_shell_locale_dict, normalize_lang
from phase47_runtime.ui_copy import build_section_payload, build_user_first_brief, navigation_contract
from phase51_runtime.cockpit_health_surface import build_cockpit_runtime_health_payload
from phase51_runtime.external_ingest_adapters import process_external_payload


def _request_lang(query: dict[str, str] | None, headers: dict[str, str] | None) -> str:
    h = headers or {}
    q = query or {}
    v = (q.get("lang") or q.get("locale") or h.get("X-User-Language") or h.get("X-Cockpit-Lang") or "").strip()
    return normalize_lang(v or None)


def _counts(state: CockpitRuntimeState) -> dict[str, int]:
    alerts = list_alerts(state.alert_ledger_path)
    decs = list_decisions(state.decision_ledger_path)
    open_alerts = sum(1 for a in alerts if str(a.get("status") or "") == "open")
    return {"open_alert_count": open_alerts, "total_alerts": len(alerts), "decision_count": len(decs)}


def api_meta(state: CockpitRuntimeState) -> dict[str, Any]:
    m = state.meta()
    m.update(_counts(state))
    return m


def api_home_feed(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    return build_home_feed_payload(state, lang=lang)


def api_overview(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    b = state.bundle
    rm = b.get("founder_read_model") or {}
    pitch = b.get("representative_pitch") or {}
    cs = b.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    c = _counts(state)
    runtime_health = build_cockpit_runtime_health_payload(repo_root=state.repo_root, lang=lang)
    return {
        "lang": lang,
        "asset_id": rm.get("asset_id"),
        "founder_primary_status": agg.get("founder_primary_status"),
        "current_stance": rm.get("current_stance"),
        "closeout_status": rm.get("closeout_status"),
        "reopen_requires_named_source": rm.get("reopen_requires_named_source"),
        "pitch_summary": (pitch.get("top_level_pitch") or "")[:800],
        "decision_card": agg.get("decision_card"),
        "counts": c,
        "runtime_health": runtime_health,
        "user_first": {
            "brief": build_user_first_brief(b, lang=lang),
            "navigation": navigation_contract(lang),
        },
    }


_USER_FIRST_SECTIONS = frozenset(
    {"brief", "why_now", "what_could_change", "evidence", "history", "ask_ai", "advanced"}
)


def api_user_first_section(state: CockpitRuntimeState, section: str, lang: str) -> dict[str, Any]:
    s = section.strip().lower()
    if s not in _USER_FIRST_SECTIONS:
        return {"ok": False, "error": "unknown_section", "allowed": sorted(_USER_FIRST_SECTIONS)}
    payload = build_section_payload(state.bundle, s, lang=lang)
    return {"ok": True, **payload}


def api_drilldown(state: CockpitRuntimeState, layer: str) -> dict[str, Any]:
    dd = state.bundle.get("drilldown_examples") or {}
    if layer not in dd:
        return {"ok": False, "error": "unknown_layer", "layer": layer}
    return {"ok": True, "layer": layer, "content": dd[layer]}


def api_alerts(
    state: CockpitRuntimeState,
    *,
    status_filter: str | None = None,
    asset_id: str | None = None,
) -> dict[str, Any]:
    rows = list_alerts(state.alert_ledger_path)
    if status_filter:
        rows = [a for a in rows if str(a.get("status") or "") == status_filter]
    if asset_id:
        rows = [a for a in rows if str(a.get("asset_id") or "") == asset_id]
    return {"ok": True, "alerts": rows}


def api_alert_action(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    action = str(body.get("action") or "").strip().lower()
    mapping = {
        "acknowledge": "acknowledged",
        "resolve": "resolved",
        "supersede": "superseded",
        "dismiss": "dismissed",
    }
    if action not in mapping:
        return {"ok": False, "error": "invalid_action", "allowed": list(mapping)}
    alert_id = body.get("alert_id")
    index = body.get("index")
    if alert_id is None and index is None:
        return {"ok": False, "error": "need_alert_id_or_index"}
    try:
        idx = int(index) if index is not None else None
    except (TypeError, ValueError):
        idx = None
    try:
        entry = update_alert_status(
            state.alert_ledger_path,
            new_status=mapping[action],
            alert_id=str(alert_id) if alert_id is not None else None,
            index=idx,
            operator_note=body.get("operator_note"),
        )
    except (KeyError, IndexError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    emit_notification(
        "alert_status_changed",
        {"alert_id": entry.get("alert_id"), "status": entry.get("status"), "action": action},
    )
    return {"ok": True, "alert": entry}


def api_decisions(
    state: CockpitRuntimeState,
    *,
    asset_id: str | None = None,
    decision_type: str | None = None,
) -> dict[str, Any]:
    rows = list_decisions(state.decision_ledger_path)
    if asset_id:
        rows = [d for d in rows if str(d.get("asset_id") or "") == asset_id]
    if decision_type:
        rows = [d for d in rows if str(d.get("decision_type") or "") == decision_type]
    return {"ok": True, "decisions": rows}


def api_decision_append(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    dt = str(body.get("decision_type") or "").strip()
    if dt not in DECISION_TYPES:
        return {"ok": False, "error": "invalid_decision_type", "allowed": sorted(DECISION_TYPES)}
    asset_id = str(body.get("asset_id") or "").strip()
    if not asset_id:
        return {"ok": False, "error": "asset_id_required"}
    note = str(body.get("founder_note") or "")[:4000]
    try:
        entry = append_decision(
            state.decision_ledger_path,
            asset_id=asset_id,
            decision_type=dt,
            founder_note=note,
            linked_message_summary=str(body.get("linked_message_summary") or "")[:2000],
            linked_authoritative_artifact=str(body.get("linked_authoritative_artifact") or "")[:2000],
            linked_research_provenance=str(body.get("linked_research_provenance") or "")[:2000],
            outcome_placeholder=body.get("outcome_placeholder"),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    emit_notification("decision_recorded", {"decision_type": dt, "asset_id": asset_id})
    return {"ok": True, "decision": entry}


def api_conversation(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    text = str(body.get("text") or "")
    try:
        out = process_governed_prompt(state.bundle, text)
    except ValueError as e:
        return {"ok": False, "error": "governance_violation", "detail": str(e)}
    return {"ok": True, "response": out}


def api_reload(state: CockpitRuntimeState) -> dict[str, Any]:
    state.reload_bundle()
    emit_notification("bundle_reloaded", {"path": str(state.phase46_bundle_path)})
    return {"ok": True, "meta": api_meta(state)}


def api_replay_timeline(state: CockpitRuntimeState) -> dict[str, Any]:
    return api_replay_timeline_payload(
        state.bundle,
        state.alert_ledger_path,
        state.decision_ledger_path,
    )


def api_replay_micro_brief(state: CockpitRuntimeState, event_id: str) -> dict[str, Any]:
    eid = str(event_id or "").strip()
    if not eid:
        return {"ok": False, "error": "event_id_required"}
    tl = api_replay_timeline(state)
    if not tl.get("ok"):
        return tl
    events = tl.get("events") or []
    mb = micro_brief_for_event(events, eid)
    if mb is None:
        return {"ok": False, "error": "unknown_event_id", "event_id": eid}
    return {"ok": True, "micro_brief": mb}


def api_runtime_health(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    return build_cockpit_runtime_health_payload(repo_root=state.repo_root, lang=lang)


def api_locale(_state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    lg = normalize_lang(lang)
    return {"ok": True, "lang": lg, "strings": export_shell_locale_dict(lg)}


def api_today_spectrum(state: CockpitRuntimeState, lang: str, horizon: str, mock_price_tick: str) -> dict[str, Any]:
    from phase47_runtime.today_spectrum import build_today_spectrum_payload

    return build_today_spectrum_payload(
        repo_root=state.repo_root,
        horizon=horizon,
        lang=lang,
        mock_price_tick=mock_price_tick,
    )


def api_today_object(
    state: CockpitRuntimeState,
    lang: str,
    query: dict[str, str],
) -> dict[str, Any]:
    from phase47_runtime.today_spectrum import build_today_object_detail_payload

    aid = (query.get("asset_id") or query.get("a") or "").strip()
    hz = (query.get("horizon") or query.get("h") or "short").strip()
    mt = (query.get("mock_price_tick") or query.get("price_tick") or "0").strip()
    if not aid:
        return {"ok": False, "error": "missing_asset_id"}
    return build_today_object_detail_payload(
        repo_root=state.repo_root,
        asset_id=aid,
        horizon=hz,
        lang=lang,
        mock_price_tick=mt,
    )


def api_external_ingest(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    from phase50_runtime.control_plane import default_control_plane_path, load_control_plane

    cp = load_control_plane(default_control_plane_path(Path(state.repo_root)))
    if not bool(cp.get("legacy_external_ingest_enabled")):
        return {
            "ok": False,
            "error": "legacy_external_ingest_disabled",
            "hint": "Use POST /api/runtime/external-ingest/authenticated or set control plane legacy_external_ingest_enabled (internal/test only).",
        }
    out = process_external_payload(body, repo_root=state.repo_root)
    entry = (out.get("registry_entry") or {}) if isinstance(out, dict) else {}
    emit_notification(
        "external_trigger_ingested",
        {
            "event_id": entry.get("event_id"),
            "status": entry.get("status"),
            "normalized_trigger_type": entry.get("normalized_trigger_type"),
        },
    )
    return out


def api_governed_external_ingest(
    state: CockpitRuntimeState,
    body: dict[str, Any],
    headers: dict[str, str] | None,
    raw_body: bytes | None = None,
) -> dict[str, Any]:
    from phase52_runtime.governed_ingress import process_governed_external_ingest

    h = headers or {}
    out = process_governed_external_ingest(
        body,
        source_id_header=str(h.get("X-Source-Id") or ""),
        webhook_secret=str(h.get("X-Webhook-Secret") or ""),
        repo_root=state.repo_root,
        raw_body=raw_body,
        http_headers=h,
    )
    entry = out.get("registry_entry") or {}
    q = out.get("queue") or {}
    if out.get("ok"):
        emit_notification(
            "external_trigger_ingested",
            {
                "event_id": entry.get("event_id") or q.get("queue_id"),
                "status": entry.get("status") or ("queued" if q else None),
                "normalized_trigger_type": entry.get("normalized_trigger_type"),
                "ingest_mode": out.get("ingest_mode"),
            },
        )
    return out


def api_replay_contract(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    _ = state
    return {
        "ok": True,
        "lang": lang,
        "traceability_views": TRACEABILITY_VIEWS,
        "primary_navigation": navigation_contract(lang)["primary_navigation"],
        "replay_surface": {
            "modes": ["replay_timeline", "counterfactual_lab"],
            "counterfactual_scaffold": build_counterfactual_scaffold(),
        },
    }


def dispatch_json(
    state: CockpitRuntimeState,
    *,
    method: str,
    path: str,
    body: bytes | None,
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    q = query or {}
    lang = _request_lang(q, headers)
    p = path.split("?", 1)[0].rstrip("/") or "/"
    raw: dict[str, Any] = {}
    _MAX_EXT_INGEST = 32768
    if (
        method == "POST"
        and p in ("/api/runtime/external-ingest", "/api/runtime/external-ingest/authenticated")
        and body
        and len(body) > _MAX_EXT_INGEST
    ):
        return 413, {"ok": False, "error": "body_too_large", "max_bytes": _MAX_EXT_INGEST}
    if body:
        try:
            raw = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return 400, {"ok": False, "error": "invalid_json"}

    if method == "GET" and p == "/api/meta":
        return 200, {"ok": True, **api_meta(state)}
    if method == "GET" and p == "/api/overview":
        return 200, {"ok": True, **api_overview(state, lang)}
    if method == "GET" and p == "/api/home/feed":
        return 200, api_home_feed(state, lang)
    if method == "GET" and p.startswith("/api/user-first/section/"):
        sec = p.split("/api/user-first/section/", 1)[-1]
        r = api_user_first_section(state, sec, lang)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p.startswith("/api/drilldown/"):
        layer = p.split("/api/drilldown/", 1)[-1]
        r = api_drilldown(state, layer)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/alerts":
        return 200, api_alerts(state, status_filter=q.get("status"), asset_id=q.get("asset_id"))
    if method == "GET" and p == "/api/decisions":
        return 200, api_decisions(state, asset_id=q.get("asset_id"), decision_type=q.get("decision_type"))
    if method == "GET" and p == "/api/notifications":
        return 200, {"ok": True, "events": list_notifications()}
    if method == "GET" and p == "/api/replay/timeline":
        r = api_replay_timeline(state)
        return (200 if r.get("ok") else 422), r
    if method == "GET" and p == "/api/replay/micro-brief":
        r = api_replay_micro_brief(state, q.get("event_id", ""))
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/replay/contract":
        return 200, api_replay_contract(state, lang)
    if method == "GET" and p == "/api/runtime/health":
        return 200, api_runtime_health(state, lang)
    if method == "GET" and p == "/api/locale":
        return 200, api_locale(state, lang)
    if method == "GET" and p == "/api/today/spectrum":
        hz = (q.get("horizon") or q.get("h") or "short").strip()
        mt = (q.get("mock_price_tick") or q.get("price_tick") or "0").strip()
        sp = api_today_spectrum(state, lang, hz, mt)
        return (200 if sp.get("ok") else 404), sp
    if method == "GET" and p == "/api/today/object":
        ob = api_today_object(state, lang, q)
        err = ob.get("error")
        if err == "missing_asset_id":
            return 400, ob
        return (200 if ob.get("ok") else 404), ob
    if method == "POST" and p == "/api/runtime/external-ingest":
        leg = api_external_ingest(state, raw)
        if not leg.get("ok") and leg.get("error") == "legacy_external_ingest_disabled":
            return 403, leg
        return 200, leg
    if method == "POST" and p == "/api/runtime/external-ingest/authenticated":
        go = api_governed_external_ingest(state, raw, headers, raw_body=body)
        code = int(go.get("http_status_hint") or 200)
        resp = {k: v for k, v in go.items() if k != "http_status_hint"}
        return code, resp
    if method == "POST" and p == "/api/reload":
        return 200, api_reload(state)
    if method == "POST" and p == "/api/alerts/action":
        r = api_alert_action(state, raw)
        return (200 if r.get("ok") else 400), r
    if method == "POST" and p == "/api/decisions":
        r = api_decision_append(state, raw)
        return (200 if r.get("ok") else 400), r
    if method == "POST" and p == "/api/conversation":
        r = api_conversation(state, raw)
        return (200 if r.get("ok") else 422), r

    return 404, {"ok": False, "error": "not_found", "path": p}
