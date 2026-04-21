"""JSON API handlers for the cockpit runtime (testable without HTTP)."""

from __future__ import annotations

import json
import urllib.parse
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
from phase47_runtime.home_feed import build_home_feed_payload, bundle_watch_candidate_asset_ids
from phase47_runtime.replay_aging_brief import build_replay_aging_brief
from phase47_runtime.sandbox_runs_ledger import append_sandbox_run, get_sandbox_run, list_sandbox_runs
from phase47_runtime.sandbox_v1 import run_sandbox_v1
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
            replay_lineage_pointer=(str(body["replay_lineage_pointer"]).strip()[:2000] if body.get("replay_lineage_pointer") is not None else None),
            message_snapshot_id=(str(body["message_snapshot_id"]).strip()[:2000] if body.get("message_snapshot_id") is not None else None),
            linked_registry_entry_id=(str(body["linked_registry_entry_id"]).strip()[:2000] if body.get("linked_registry_entry_id") is not None else None),
            linked_artifact_id=(str(body["linked_artifact_id"]).strip()[:2000] if body.get("linked_artifact_id") is not None else None),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    emit_notification("decision_recorded", {"decision_type": dt, "asset_id": asset_id})
    return {"ok": True, "decision": entry}


def api_conversation(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    text = str(body.get("text") or "")
    raw_ctx = body.get("copilot_context")
    copilot_ctx: dict[str, Any] | None = raw_ctx if isinstance(raw_ctx, dict) else None
    sid = str(body.get("message_snapshot_id") or "").strip()
    if not sid and isinstance(copilot_ctx, dict):
        sid = str(copilot_ctx.get("message_snapshot_id") or "").strip()
    if sid:
        from metis_brain.message_snapshot_copilot_bridge_v0 import enrich_copilot_context_from_message_snapshot

        merged, err = enrich_copilot_context_from_message_snapshot(
            state.repo_root, sid, copilot_ctx
        )
        if err:
            return {
                "ok": False,
                "error": err,
                "message_snapshot_id": sid,
                "contract": "GOVERNED_CONVERSATION_MESSAGE_SNAPSHOT_V0",
            }
        copilot_ctx = merged
    try:
        out = process_governed_prompt(state.bundle, text, copilot_context=copilot_ctx)
    except ValueError as e:
        return {"ok": False, "error": "governance_violation", "detail": str(e)}
    resp: dict[str, Any] = {"ok": True, "response": out}
    if sid:
        resp["message_snapshot_id"] = sid
    return resp


def api_sandbox_run(state: CockpitRuntimeState, body: dict[str, Any], lang: str) -> dict[str, Any]:
    out = run_sandbox_v1(bundle=state.bundle, repo_root=state.repo_root, body=body, lang=lang)
    if out.get("ok") and body.get("save") is not False:
        try:
            append_sandbox_run(state.sandbox_ledger_path, out)
            out = {**out, "persisted": True}
        except (OSError, ValueError, TypeError):
            out = {**out, "persisted": False}
    return out


def api_sandbox_runs_list(state: CockpitRuntimeState, limit: int) -> dict[str, Any]:
    return {"ok": True, "runs": list_sandbox_runs(state.sandbox_ledger_path, limit=limit)}


def api_sandbox_run_get(state: CockpitRuntimeState, run_id: str) -> dict[str, Any]:
    row = get_sandbox_run(state.sandbox_ledger_path, run_id)
    if not row:
        return {"ok": False, "error": "unknown_run_id", "run_id": run_id}
    return {"ok": True, "run": row, "source": "ledger"}


def _build_harness_store_for_api(
    use_fixture: bool = False,
) -> Any:
    """Lazy build of the harness store for sandbox / governance-lineage
    read APIs. Import is deferred so non-harness routes do not pull the
    harness module graph."""

    from agentic_harness.runtime import build_store

    return build_store(use_fixture=use_fixture)


def api_sandbox_requests_list(
    state: CockpitRuntimeState,
    *,
    registry_entry_id: str | None = None,
    horizon: str | None = None,
    limit: int = 40,
    use_fixture: bool = False,
) -> dict[str, Any]:
    """AGH v1 Patch 5 — list recent ``SandboxRequestPacketV1`` packets
    (optionally filtered by ``registry_entry_id`` / ``horizon``) and
    attach the matching ``SandboxResultPacketV1`` when one exists.

    The active registry is never read from this path; Today keeps its
    own registry-only surface.
    """

    try:
        store = _build_harness_store_for_api(use_fixture=use_fixture)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"harness_store_unavailable:{exc}",
            "contract": "AGH_V1_SANDBOX_REQUESTS_LIST",
        }
    try:
        requests = list(
            store.list_packets(packet_type="SandboxRequestPacketV1", limit=max(limit, 1))
            or []
        )
        results = list(
            store.list_packets(packet_type="SandboxResultPacketV1", limit=max(limit, 1) * 2)
            or []
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"packet_list_failed:{exc}",
            "contract": "AGH_V1_SANDBOX_REQUESTS_LIST",
        }

    # AGH v1 Patch 8 B2 — join the sandbox_queue job record (if any) for
    # each request so the UI can render the true 4-state lifecycle
    # (queued / running / completed / blocked) rather than inferring state
    # from the presence of a result packet alone. A blocked request (DLQ
    # or expired) still has no SandboxResultPacketV1, but now the
    # operator can see that it is NOT merely queued.
    try:
        all_jobs = list(
            store.list_jobs(queue_class="sandbox_queue", limit=max(limit, 1) * 4) or []
        )
    except Exception:
        all_jobs = []
    jobs_by_packet: dict[str, dict[str, Any]] = {}
    for job in all_jobs:
        pid = str((job or {}).get("packet_id") or "")
        if not pid:
            continue
        prev = jobs_by_packet.get(pid)
        if prev is None or str(job.get("enqueued_at_utc") or "") > str(
            prev.get("enqueued_at_utc") or ""
        ):
            jobs_by_packet[pid] = job

    rid = (registry_entry_id or "").strip()
    hz = (horizon or "").strip()

    def _match(pkt: dict[str, Any]) -> bool:
        payload = pkt.get("payload") or {}
        if rid and str(payload.get("registry_entry_id") or "") != rid:
            return False
        if hz and str(payload.get("horizon") or "") != hz:
            return False
        return True

    matched = [p for p in requests if _match(p)]
    matched.sort(key=lambda r: str(r.get("created_at_utc") or ""), reverse=True)
    matched = matched[:limit]

    def _result_for(req_pid: str) -> dict[str, Any] | None:
        for r in results:
            payload = r.get("payload") or {}
            if str(payload.get("cited_request_packet_id") or "") == req_pid:
                return r
        return None

    def _life_state(job: dict[str, Any] | None, result: dict[str, Any] | None) -> str:
        # AGH v1 Patch 8 B2 — deterministic 4-state mapping. Precedence:
        # result packet present → completed; job dlq/expired → blocked;
        # job running → running; otherwise → queued. This is the SINGLE
        # source of truth for the TSR invoke chip + per-entry recent list.
        if result:
            return "completed"
        if job:
            js = str(job.get("status") or "").lower()
            if js in ("dlq", "expired"):
                return "blocked"
            if js == "running":
                return "running"
            if js == "done":
                return "completed"
        return "queued"

    items: list[dict[str, Any]] = []
    for req in matched:
        req_pid = str(req.get("packet_id") or "")
        job = jobs_by_packet.get(req_pid)
        result = _result_for(req_pid)
        items.append(
            {
                "request": req,
                "result": result,
                "job": job,
                "job_status": str((job or {}).get("status") or "") or None,
                "lifecycle_state": _life_state(job, result),
            }
        )

    return {
        "ok": True,
        "contract": "AGH_V1_SANDBOX_REQUESTS_LIST",
        "registry_entry_id": rid or None,
        "horizon": hz or None,
        "requests": items,
        "count": len(items),
    }


def api_sandbox_enqueue_v1(
    state: CockpitRuntimeState,
    body: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """AGH v1 Patch 6 — operator-gated thin POST endpoint.

    Guarded by ``METIS_HARNESS_UI_INVOKE_ENABLED=1``. When enabled, the UI
    can click "Enqueue via UI (operator-gated)" and the server calls
    ``layer3_sandbox_executor_v1.enqueue_sandbox_request`` on the real
    store. The worker tick is still a separate CLI invocation
    (``harness-tick --queue sandbox_queue``). The server never executes
    the sandbox autonomously.

    Returns ``(http_status, body)`` so ``dispatch_json`` does not need to
    infer the status from the payload.
    """

    _ = state
    import os as _os

    gated = _os.environ.get("METIS_HARNESS_UI_INVOKE_ENABLED", "0").strip() == "1"
    if not gated:
        return 403, {
            "ok": False,
            "error": "ui_invoke_disabled",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
            "hint": (
                "Set METIS_HARNESS_UI_INVOKE_ENABLED=1 to enable the "
                "operator-gated UI enqueue path, or copy-paste the "
                "harness-sandbox-request CLI string."
            ),
        }

    from agentic_harness.contracts.packets_v1 import SANDBOX_KINDS

    required_top = (
        "sandbox_kind",
        "registry_entry_id",
        "horizon",
        "target_spec",
        "rationale",
        "cited_evidence_packet_ids",
    )
    missing = [k for k in required_top if k not in (body or {})]
    if missing:
        return 400, {
            "ok": False,
            "error": f"missing_fields:{','.join(missing)}",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    kind = str(body.get("sandbox_kind") or "").strip()
    if kind not in SANDBOX_KINDS:
        return 400, {
            "ok": False,
            "error": (
                f"sandbox_kind_not_allowed:{kind!r} (allowed={list(SANDBOX_KINDS)})"
            ),
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    target_spec = body.get("target_spec") or {}
    if not isinstance(target_spec, dict):
        return 400, {
            "ok": False,
            "error": "target_spec_must_be_object",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }
    if kind == "validation_rerun":
        for k in ("factor_name", "universe_name", "horizon_type", "return_basis"):
            if not str(target_spec.get(k) or "").strip():
                return 400, {
                    "ok": False,
                    "error": f"target_spec_missing:{k}",
                    "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
                }

    rid = str(body.get("registry_entry_id") or "").strip()
    horizon = str(body.get("horizon") or "").strip()
    if not rid or not horizon:
        return 400, {
            "ok": False,
            "error": "registry_entry_id_and_horizon_required",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    rationale = str(body.get("rationale") or "").strip()
    if not rationale or len(rationale) > 500:
        return 400, {
            "ok": False,
            "error": "rationale_must_be_1_to_500_chars",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    cited_raw = body.get("cited_evidence_packet_ids") or []
    if not isinstance(cited_raw, list) or not cited_raw:
        return 400, {
            "ok": False,
            "error": "cited_evidence_packet_ids_must_be_non_empty_list",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }
    cited = [str(x).strip() for x in cited_raw if str(x or "").strip()]
    if not cited:
        return 400, {
            "ok": False,
            "error": "cited_evidence_packet_ids_must_be_non_empty_list",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    request_id = str(body.get("request_id") or "").strip()
    if not request_id:
        import uuid as _uuid

        request_id = f"ui-op-{_uuid.uuid4()}"

    # SandboxRequestPacketV1 restricts ``requested_by`` to
    # ``SANDBOX_REQUEST_ACTORS`` = ("operator", "research_ask_v1"). UI-gated
    # enqueue is an explicit operator action, so we default to "operator"
    # (the CLI also uses "operator"). Callers may override only to another
    # allowed value.
    from agentic_harness.contracts.packets_v1 import SANDBOX_REQUEST_ACTORS

    requested_by_raw = str(body.get("requested_by") or "operator").strip()[:120]
    requested_by = requested_by_raw if requested_by_raw in SANDBOX_REQUEST_ACTORS else "operator"
    use_fixture = bool(body.get("use_fixture") or False)

    try:
        store = _build_harness_store_for_api(use_fixture=use_fixture)
    except Exception as exc:
        return 500, {
            "ok": False,
            "error": f"harness_store_unavailable:{exc}",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }

    from agentic_harness.agents.layer3_sandbox_executor_v1 import (
        enqueue_sandbox_request,
    )

    try:
        res = enqueue_sandbox_request(
            store,
            request_id=request_id,
            sandbox_kind=kind,
            registry_entry_id=rid,
            horizon=horizon,
            target_spec=target_spec,
            requested_by=requested_by,
            cited_evidence_packet_ids=cited,
            cited_ask_packet_id=(
                str(body.get("cited_ask_packet_id") or "").strip() or None
            ),
        )
    except Exception as exc:
        return 500, {
            "ok": False,
            "error": f"enqueue_failed:{exc}",
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        }
    if not res.get("ok"):
        return 400, {
            "ok": False,
            "error": res.get("error"),
            "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
            "rationale_echo": rationale,
        }
    emit_notification(
        "sandbox_request_enqueued_via_ui",
        {
            "request_packet_id": res.get("request_packet_id"),
            "job_id": res.get("job_id"),
            "registry_entry_id": rid,
            "horizon": horizon,
            "sandbox_kind": kind,
        },
    )
    return 200, {
        "ok": True,
        "contract": "AGH_V1_SANDBOX_ENQUEUE_V1",
        "request_packet_id": res.get("request_packet_id"),
        "job_id": res.get("job_id"),
        "cli_hint": "harness-tick --queue sandbox_queue",
        "operator_note": (
            "Request enqueued. Execute `harness-tick --queue sandbox_queue` "
            "on the operator terminal to run the sandbox worker."
        ),
    }


REPLAY_LINEAGE_DEFAULT_LIMIT = 200
REPLAY_LINEAGE_MAX_LIMIT = 500


def api_replay_governance_lineage(
    state: CockpitRuntimeState,
    *,
    registry_entry_id: str,
    horizon: str | None = None,
    use_fixture: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """AGH v1 Patch 5 — expose ``api_governance_lineage_for_registry_entry``
    (validation evaluations + governance chain + sandbox followups) so
    Replay can render a full lineage browser without a new subgraph.

    AGH v1 Patch 7 C2c: ``limit`` is now operator-controllable via query
    param (default ``REPLAY_LINEAGE_DEFAULT_LIMIT`` = 200, capped at
    ``REPLAY_LINEAGE_MAX_LIMIT`` = 500). Default keeps prior behavior.
    """

    from phase47_runtime.traceability_replay import (
        api_governance_lineage_for_registry_entry,
    )

    rid = (registry_entry_id or "").strip()
    if not rid:
        return {
            "ok": False,
            "error": "registry_entry_id_required",
            "contract": "AGH_V1_REPLAY_GOVERNANCE_LINEAGE",
        }
    try:
        store = _build_harness_store_for_api(use_fixture=use_fixture)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"harness_store_unavailable:{exc}",
            "contract": "AGH_V1_REPLAY_GOVERNANCE_LINEAGE",
        }
    effective_limit = REPLAY_LINEAGE_DEFAULT_LIMIT
    if limit is not None:
        try:
            effective_limit = max(1, min(int(limit), REPLAY_LINEAGE_MAX_LIMIT))
        except (TypeError, ValueError):
            effective_limit = REPLAY_LINEAGE_DEFAULT_LIMIT
    res = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id=rid,
        horizon=(horizon or "").strip(),
        limit=effective_limit,
    )
    res.setdefault("contract", "AGH_V1_REPLAY_GOVERNANCE_LINEAGE")
    res.setdefault("limit", effective_limit)
    return res


def api_reload(state: CockpitRuntimeState) -> dict[str, Any]:
    state.reload_bundle()
    emit_notification("bundle_reloaded", {"path": str(state.phase46_bundle_path)})
    return {"ok": True, "meta": api_meta(state)}


def api_replay_timeline(state: CockpitRuntimeState, q: dict[str, str] | None = None) -> dict[str, Any]:
    q = q or {}
    lang = _request_lang(q, None)
    return api_replay_timeline_payload(
        state.bundle,
        state.alert_ledger_path,
        state.decision_ledger_path,
        repo_root=state.repo_root,
        timeline_asset_id=(q.get("asset_id") or "").strip() or None,
        horizon=q.get("horizon"),
        lang=lang,
        mock_price_tick=q.get("mock_price_tick"),
    )


def api_replay_aging_brief(state: CockpitRuntimeState, lang: str, asset_id: str) -> dict[str, Any]:
    return build_replay_aging_brief(
        repo_root=state.repo_root,
        decision_ledger_path=state.decision_ledger_path,
        sandbox_ledger_path=state.sandbox_ledger_path,
        asset_id=asset_id,
        lang=lang,
    )


def api_replay_micro_brief(state: CockpitRuntimeState, event_id: str, q: dict[str, str] | None = None) -> dict[str, Any]:
    eid = str(event_id or "").strip()
    if not eid:
        return {"ok": False, "error": "event_id_required"}
    tl = api_replay_timeline(state, q)
    if not tl.get("ok"):
        return tl
    events = tl.get("events") or []
    mb = micro_brief_for_event(events, eid)
    if mb is None:
        return {"ok": False, "error": "unknown_event_id", "event_id": eid}
    return {"ok": True, "micro_brief": mb}


def api_runtime_health(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    # AGH v1 Patch 8 E2 — the payload builder never raises for recoverable
    # sub-failures; it returns health_status='degraded' + reasons. The
    # only exception path that lands here is a catastrophic import /
    # filesystem failure, in which case we return an 'ok:false' shape
    # the HTTP layer maps to 503.
    try:
        return build_cockpit_runtime_health_payload(repo_root=state.repo_root, lang=lang)
    except Exception as exc:  # pragma: no cover — guarded path
        return {
            "ok": False,
            "health_status": "down",
            "degraded_reasons": [f"runtime_health_exception: {type(exc).__name__}"],
            "lang": lang,
        }


def api_locale(_state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    lg = normalize_lang(lang)
    return {"ok": True, "lang": lg, "strings": export_shell_locale_dict(lg)}


def api_today_spectrum(
    state: CockpitRuntimeState,
    lang: str,
    horizon: str,
    mock_price_tick: str,
    rows_limit: int | None = None,
) -> dict[str, Any]:
    from phase47_runtime.today_spectrum import build_today_spectrum_payload

    return build_today_spectrum_payload(
        rows_limit=rows_limit,
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


def api_demo_frozen_snapshot_pack(state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    from phase47_runtime.frozen_snapshot_pack_v0 import load_frozen_snapshot_pack_v0

    return load_frozen_snapshot_pack_v0(state.repo_root, lang=lang)


def api_today_watchlist_order_get(state: CockpitRuntimeState) -> dict[str, Any]:
    from phase47_runtime.watchlist_order_v1 import load_watchlist_order, merge_watchlist_display_order

    canon = bundle_watch_candidate_asset_ids(state.bundle)
    stored = load_watchlist_order(state.repo_root)
    merged = merge_watchlist_display_order(canon, stored)
    return {
        "ok": True,
        "contract": "WATCHLIST_ORDER_V1",
        "bundle_watch_ids": canon,
        "stored_raw_order": stored,
        "effective_ordered_ids": merged,
    }


def api_today_watchlist_order_post(state: CockpitRuntimeState, body: dict[str, Any]) -> dict[str, Any]:
    from phase47_runtime.watchlist_order_v1 import (
        load_watchlist_order,
        merge_watchlist_display_order,
        save_watchlist_order,
        validate_full_reorder_payload,
    )

    canon = bundle_watch_candidate_asset_ids(state.bundle)
    ordered, err = validate_full_reorder_payload(body.get("ordered_asset_ids"), allowed_ordered=canon)
    if err:
        return {"ok": False, "error": err, "contract": "WATCHLIST_ORDER_V1", "bundle_watch_ids": canon}
    save_watchlist_order(state.repo_root, ordered)
    stored = load_watchlist_order(state.repo_root)
    return {
        "ok": True,
        "contract": "WATCHLIST_ORDER_V1",
        "ordered_asset_ids": stored,
        "effective_ordered_ids": merge_watchlist_display_order(canon, stored),
    }


def api_resolve_message_snapshot(state: CockpitRuntimeState, q: dict[str, str]) -> dict[str, Any]:
    """Resolve a persisted Today row snapshot by id (Product Spec §5.2–5.3, §6.4 — shared by Today + Replay)."""
    from metis_brain.message_snapshots_store import get_message_snapshot

    sid = (q.get("snapshot_id") or q.get("message_snapshot_id") or "").strip()
    if not sid:
        return {"ok": False, "error": "snapshot_id_required", "contract": "MESSAGE_SNAPSHOT_RESOLVE_V1"}
    row = get_message_snapshot(state.repo_root, sid)
    if not row:
        return {
            "ok": False,
            "error": "snapshot_not_found",
            "snapshot_id": sid,
            "contract": "MESSAGE_SNAPSHOT_RESOLVE_V1",
        }
    out: dict[str, Any] = {"ok": True, "contract": "MESSAGE_SNAPSHOT_RESOLVE_V1", "snapshot_id": sid, "snapshot": row}
    rs = row.get("registry_surface_v1")
    if isinstance(rs, dict):
        out["registry_surface_v1"] = rs
    return out


def api_counterfactual_templates(_state: CockpitRuntimeState, lang: str) -> dict[str, Any]:
    from phase47_runtime.replay_counterfactual_v1 import counterfactual_templates_v1_payload

    return counterfactual_templates_v1_payload(lang)


def api_counterfactual_preview(state: CockpitRuntimeState, q: dict[str, str], lang: str) -> dict[str, Any]:
    from phase47_runtime.replay_counterfactual_v1 import counterfactual_preview_v1

    return counterfactual_preview_v1(
        repo_root=state.repo_root,
        template_id=str(q.get("template_id") or ""),
        asset_id=str(q.get("asset_id") or ""),
        horizon=str(q.get("horizon") or "short"),
        lang=lang,
        mock_price_tick=q.get("mock_price_tick"),
    )


def dispatch_json(
    state: CockpitRuntimeState,
    *,
    method: str,
    path: str,
    body: bytes | None,
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    path_part, sep, qs = path.partition("?")
    q: dict[str, str] = {}
    if sep:
        for k, v in urllib.parse.parse_qsl(qs, keep_blank_values=True):
            q[k] = v
    if query:
        q.update(query)
    lang = _request_lang(q, headers)
    p = path_part.rstrip("/") or "/"
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
        r = api_replay_timeline(state, q)
        return (200 if r.get("ok") else 422), r
    if method == "GET" and p == "/api/replay/aging-brief":
        aid = (q.get("asset_id") or "").strip()
        if not aid:
            return 400, {"ok": False, "error": "asset_id_required", "contract": "REPLAY_AGING_BRIEF_V1"}
        return 200, api_replay_aging_brief(state, lang, aid)
    if method == "GET" and p == "/api/replay/micro-brief":
        r = api_replay_micro_brief(state, q.get("event_id", ""), q)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/replay/message-snapshot":
        r = api_resolve_message_snapshot(state, q)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/today/message-snapshot":
        r = api_resolve_message_snapshot(state, q)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/replay/counterfactual-templates":
        return 200, api_counterfactual_templates(state, lang)
    if method == "GET" and p == "/api/replay/counterfactual-preview":
        r = api_counterfactual_preview(state, q, lang)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/replay/contract":
        return 200, api_replay_contract(state, lang)
    if method == "GET" and p == "/api/demo/frozen-snapshot-pack":
        r = api_demo_frozen_snapshot_pack(state, lang)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/runtime/health":
        # AGH v1 Patch 8 E2 — 'degraded' is a 200 (operator still needs
        # to navigate); only 'down' (catastrophic) is 503. The payload
        # always carries health_status + degraded_reasons.
        hr = api_runtime_health(state, lang)
        status = str((hr or {}).get("health_status") or "")
        code = 503 if status == "down" else 200
        return code, hr
    if method == "GET" and p == "/api/locale":
        return 200, api_locale(state, lang)
    if method == "GET" and p == "/api/today/spectrum":
        hz = (q.get("horizon") or q.get("h") or "short").strip()
        mt = (q.get("mock_price_tick") or q.get("price_tick") or "0").strip()
        raw_rows_limit = q.get("rows_limit") or q.get("limit")
        rl: int | None
        try:
            rl = int(raw_rows_limit) if raw_rows_limit not in (None, "") else None
        except ValueError:
            rl = None
        sp = api_today_spectrum(state, lang, hz, mt, rows_limit=rl)
        return (200 if sp.get("ok") else 404), sp
    if method == "GET" and p == "/api/today/watchlist-order":
        return 200, api_today_watchlist_order_get(state)
    if method == "POST" and p == "/api/today/watchlist-order":
        r = api_today_watchlist_order_post(state, raw)
        return (200 if r.get("ok") else 400), r
    if method == "GET" and p == "/api/sandbox/runs":
        try:
            lim = int(q.get("limit") or "40")
        except ValueError:
            lim = 40
        return 200, api_sandbox_runs_list(state, lim)
    if method == "GET" and p == "/api/sandbox/run":
        rid = (q.get("run_id") or "").strip()
        if not rid:
            return 400, {"ok": False, "error": "run_id_required", "contract": "SANDBOX_V1"}
        r = api_sandbox_run_get(state, rid)
        return (200 if r.get("ok") else 404), r
    if method == "GET" and p == "/api/sandbox/requests":
        try:
            lim = int(q.get("limit") or "40")
        except ValueError:
            lim = 40
        use_fixture = (q.get("use_fixture") or "").strip().lower() in {"1", "true", "yes"}
        r = api_sandbox_requests_list(
            state,
            registry_entry_id=q.get("registry_entry_id"),
            horizon=q.get("horizon"),
            limit=lim,
            use_fixture=use_fixture,
        )
        return (200 if r.get("ok") else 500), r
    if method == "GET" and p == "/api/replay/governance-lineage":
        rid = (q.get("registry_entry_id") or "").strip()
        if not rid:
            return 400, {
                "ok": False,
                "error": "registry_entry_id_required",
                "contract": "AGH_V1_REPLAY_GOVERNANCE_LINEAGE",
            }
        use_fixture = (q.get("use_fixture") or "").strip().lower() in {"1", "true", "yes"}
        raw_lineage_limit = q.get("limit")
        lineage_limit: int | None
        try:
            lineage_limit = (
                int(raw_lineage_limit)
                if raw_lineage_limit not in (None, "")
                else None
            )
        except ValueError:
            lineage_limit = None
        r = api_replay_governance_lineage(
            state,
            registry_entry_id=rid,
            horizon=q.get("horizon"),
            use_fixture=use_fixture,
            limit=lineage_limit,
        )
        return (200 if r.get("ok") else 500), r
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
    if method == "POST" and p == "/api/sandbox/run":
        r = api_sandbox_run(state, raw, lang)
        return (200 if r.get("ok") else 400), r
    if method == "POST" and p == "/api/sandbox/enqueue":
        status, r = api_sandbox_enqueue_v1(state, raw)
        return status, r

    return 404, {"ok": False, "error": "not_found", "path": p}
