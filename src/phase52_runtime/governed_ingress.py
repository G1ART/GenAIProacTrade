"""Authenticated, budgeted, routed external ingest (Phase 52)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase50_runtime.control_plane import default_control_plane_path, load_control_plane

from phase51_runtime.external_ingest_adapters import process_external_payload
from phase51_runtime.external_trigger_audit import append_external_audit, audit_ingest_outcome, default_external_trigger_audit_path
from phase51_runtime.external_trigger_ingest import default_ingest_registry_path, ingest_external_event
from phase51_runtime.trigger_normalizer import compute_dedupe_key, normalize_raw_event

from phase52_runtime.event_queue import default_event_queue_path, enqueue_event, mark_queue_item_consumed
from phase52_runtime.routing_rules import routing_allows_event
from phase52_runtime.source_budgets import (
    check_and_consume_budget,
    default_budget_state_path,
    record_auth_failure,
    record_outcome,
    record_routing_rejection,
)
from phase52_runtime.webhook_auth import verify_source_auth
from phase52_runtime.source_registry import default_external_source_registry_path, find_source_by_id, load_source_registry


def _audit_gate(
    audit_path: Path,
    *,
    kind: str,
    source_id: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {
        "kind": kind,
        "source_id": source_id,
        "gate_reason": reason,
        "ingest_path": "phase52_governed",
    }
    if extra:
        row.update(extra)
    append_external_audit(audit_path, row)


def process_governed_external_ingest(
    body: dict[str, Any],
    *,
    source_id_header: str,
    webhook_secret: str,
    repo_root: Path,
    source_registry_path: Path | None = None,
    budget_state_path: Path | None = None,
    queue_path: Path | None = None,
    ingest_registry_path: Path | None = None,
    audit_path: Path | None = None,
    control_plane_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Headers (HTTP): X-Source-Id, X-Webhook-Secret (plain secret; TLS required in production).

    Returns JSON including `ok` (accepted or queued), `http_status_hint`, `gate_reason` on failure.
    """
    now = now or datetime.now(timezone.utc)
    reg_p = source_registry_path or default_external_source_registry_path(repo_root)
    bud_p = budget_state_path or default_budget_state_path(repo_root)
    q_p = queue_path or default_event_queue_path(repo_root)
    ap = audit_path or default_external_trigger_audit_path(repo_root)
    cp_path = control_plane_path or default_control_plane_path(repo_root)
    cp = load_control_plane(cp_path)

    sid = str(source_id_header or "").strip()
    if not sid:
        _audit_gate(ap, kind="phase52_auth_failure", source_id="", reason="missing_source_id_header")
        return {"ok": False, "http_status_hint": 401, "error": "missing_source_id", "gate_reason": "missing_source_id"}

    reg = load_source_registry(reg_p)
    src = find_source_by_id(reg, sid)
    if not src:
        _audit_gate(ap, kind="phase52_auth_failure", source_id=sid, reason="unknown_source_id")
        record_auth_failure(source_id=sid, budget_path=bud_p, reason="unknown_source_id", now=now)
        record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_unknown_source", now=now)
        return {"ok": False, "http_status_hint": 403, "error": "unknown_source", "gate_reason": "unknown_source_id"}

    ok_auth, auth_reason = verify_source_auth(src, presented_secret=webhook_secret)
    if not ok_auth:
        _audit_gate(
            ap,
            kind="phase52_auth_failure",
            source_id=sid,
            reason=auth_reason,
            extra={"raw_event_type": body.get("raw_event_type")},
        )
        record_auth_failure(source_id=sid, budget_path=bud_p, reason=auth_reason, now=now)
        record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_auth", now=now)
        return {"ok": False, "http_status_hint": 401, "error": "auth_failed", "gate_reason": auth_reason}

    norm = normalize_raw_event(body)
    if not norm.get("ok"):
        reason = str(norm.get("reason") or "normalize_failed")
        _audit_gate(ap, kind="phase52_normalize_rejected", source_id=sid, reason=reason)
        record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_normalize", now=now)
        return {"ok": False, "http_status_hint": 422, "error": "normalize_failed", "gate_reason": reason}

    nt = str(norm.get("normalized_trigger_type") or "")
    raw_t = str(body.get("raw_event_type") or "").strip()
    ok_route, route_reason = routing_allows_event(source=src, raw_event_type=raw_t, normalized_trigger_type=nt)
    if not ok_route:
        _audit_gate(ap, kind="phase52_routing_rejected", source_id=sid, reason=route_reason)
        record_routing_rejection(source_id=sid, budget_path=bud_p, reason=route_reason, now=now)
        record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_routing", now=now)
        return {"ok": False, "http_status_hint": 403, "error": "routing_rejected", "gate_reason": route_reason}

    ok_budget, budget_reason = check_and_consume_budget(source=src, source_id=sid, budget_path=bud_p, now=now)
    if not ok_budget:
        _audit_gate(ap, kind="phase52_rate_limited", source_id=sid, reason=budget_reason)
        record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_rate", now=now)
        return {"ok": False, "http_status_hint": 429, "error": "rate_limited", "gate_reason": budget_reason}

    queue_mode = str(src.get("queue_mode") or "direct").strip().lower()
    pl = dict(body.get("payload") or {})
    dk_preview = compute_dedupe_key(
        source_type=str(body.get("source_type") or src.get("source_type") or "webhook"),
        source_id=sid,
        raw_event_type=raw_t,
        payload=pl,
    )

    if queue_mode in ("enqueue_before_cycle", "queue", "enqueue"):
        qres = enqueue_event(path=q_p, body=body, dedupe_key=dk_preview, source_id=sid, max_depth=int(src.get("queue_max_depth") or 500))
        if not qres.get("ok"):
            record_outcome(source_id=sid, budget_path=bud_p, outcome="rejected_queue", now=now)
            return {
                "ok": False,
                "http_status_hint": 409 if qres.get("reason") == "duplicate_pending_dedupe_key" else 503,
                "error": qres.get("reason"),
                "gate_reason": str(qres.get("reason")),
                "queue": qres,
            }
        record_outcome(source_id=sid, budget_path=bud_p, outcome="queued", now=now)
        append_external_audit(
            ap,
            {
                "kind": "phase52_queued",
                "source_id": sid,
                "dedupe_key": dk_preview,
                "queue_id": qres.get("queue_id"),
                "queue_depth_pending": qres.get("queue_depth_pending"),
            },
        )
        return {
            "ok": True,
            "http_status_hint": 202,
            "ingest_mode": "queued",
            "queue": qres,
            "dedupe_key": dk_preview,
        }

    out = process_external_payload(
        body,
        repo_root=repo_root,
        ingest_registry_path=ingest_registry_path,
        audit_path=ap,
        control_plane_path=cp_path,
        maintenance_blocks_accept=False,
    )
    entry = out.get("registry_entry") or {}
    record_outcome(
        source_id=sid,
        budget_path=bud_p,
        outcome="accepted_registry" if entry.get("status") == "accepted" else "registry_other",
        now=now,
    )
    return {
        **out,
        "http_status_hint": 200,
        "ingest_mode": "direct",
        "source_id": sid,
    }


def flush_one_queued_event_to_registry(
    *,
    repo_root: Path,
    queue_path: Path | None = None,
    ingest_registry_path: Path | None = None,
    audit_path: Path | None = None,
    control_plane_path: Path | None = None,
) -> dict[str, Any]:
    """Pop one pending queue item and run governed registry ingest (Phase 51 path)."""
    from phase52_runtime.event_queue import mark_queue_item_status, pop_next_pending

    q_p = queue_path or default_event_queue_path(repo_root)
    ap = audit_path or default_external_trigger_audit_path(repo_root)
    cp_path = control_plane_path or default_control_plane_path(repo_root)
    cp = load_control_plane(cp_path)
    item = pop_next_pending(q_p)
    if not item:
        return {"ok": False, "error": "queue_empty"}
    body = item.get("body") or {}
    qid = str(item.get("queue_id") or "")
    ing_p = ingest_registry_path or default_ingest_registry_path(repo_root)
    norm = normalize_raw_event(body)
    if not norm.get("ok"):
        mark_queue_item_status(q_p, qid, "rejected_after_dequeue")
        return {"ok": False, "error": "normalize_failed_on_flush", "reason": norm.get("reason")}
    ent = ingest_external_event(
        body,
        ingest_registry_path=ing_p,
        control_plane=cp,
        maintenance_blocks_accept=False,
    )
    deduped = ent.get("status") == "deduped"
    audit_ingest_outcome(
        ap,
        raw_event=body,
        registry_entry=ent,
        normalization_ok=True,
        normalization_reason=None,
        deduped=deduped,
        consumed_by_cycle_id=None,
    )
    mark_queue_item_consumed(q_p, qid)
    return {"ok": True, "registry_entry": ent, "queue_id": qid}
