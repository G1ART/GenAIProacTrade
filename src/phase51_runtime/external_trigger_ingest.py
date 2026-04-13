"""Persistent external trigger ingest registry (v1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase48_runtime.job_registry import JOB_TYPES

from phase51_runtime.trigger_normalizer import compute_dedupe_key, normalize_raw_event

from phase50_runtime.trigger_controls import effective_budget_policy


def default_ingest_registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_trigger_ingest_v1.json"


def load_ingest_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "entries": []}


def save_ingest_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def existing_dedupe_keys(path: Path) -> set[str]:
    reg = load_ingest_registry(path)
    return {str(e.get("dedupe_key") or "") for e in (reg.get("entries") or []) if e.get("dedupe_key")}


def link_events_to_cycle(path: Path, event_ids: list[str], cycle_id: str) -> None:
    reg = load_ingest_registry(path)
    ids = set(event_ids)
    for e in reg.get("entries") or []:
        if str(e.get("event_id") or "") in ids:
            e["linked_cycle_id"] = cycle_id
            e["status"] = "consumed"
    save_ingest_registry(path, reg)


def ingest_external_event(
    raw: dict[str, Any],
    *,
    ingest_registry_path: Path,
    control_plane: dict[str, Any],
    maintenance_blocks_accept: bool = False,
) -> dict[str, Any]:
    """
    Validate, normalize, dedupe, control-plane gate; append registry row.
    Returns the entry dict (always includes event_id).
    """
    received_at = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid.uuid4())
    base = {
        "event_id": event_id,
        "received_at": received_at,
        "source_type": str(raw.get("source_type") or "").strip() or "unknown",
        "source_id": str(raw.get("source_id") or "").strip() or "unknown",
        "raw_event_type": str(raw.get("raw_event_type") or "").strip(),
        "normalized_trigger_type": None,
        "asset_scope": raw.get("asset_scope") if isinstance(raw.get("asset_scope"), dict) else {},
        "status": "rejected",
        "dedupe_key": "",
        "accepted_or_rejected_reason": "",
        "linked_cycle_id": None,
        "normalized_payload": None,
    }
    if maintenance_blocks_accept and control_plane.get("maintenance_mode"):
        base["accepted_or_rejected_reason"] = "maintenance_mode_ingest_suppressed"
        _append_entry(ingest_registry_path, base)
        return base

    norm = normalize_raw_event(raw)
    if not norm.get("ok"):
        base["accepted_or_rejected_reason"] = str(norm.get("reason") or "normalize_failed")
        _append_entry(ingest_registry_path, base)
        return base

    nt = str(norm["normalized_trigger_type"])
    pol = effective_budget_policy(control_plane)
    allowed = set(pol.get("allowed_trigger_types") or [])
    if nt not in allowed:
        base["normalized_trigger_type"] = nt
        base["normalized_payload"] = norm.get("normalized_payload")
        base["accepted_or_rejected_reason"] = "trigger_type_disabled_or_not_allowed"
        _append_entry(ingest_registry_path, base)
        return base

    payload = dict(norm["normalized_payload"] or {})
    dk = compute_dedupe_key(
        source_type=base["source_type"],
        source_id=base["source_id"],
        raw_event_type=base["raw_event_type"],
        payload=dict(raw.get("payload") or {}),
    )
    if dk in existing_dedupe_keys(ingest_registry_path):
        base.update(
            {
                "normalized_trigger_type": nt,
                "normalized_payload": norm.get("normalized_payload"),
                "dedupe_key": dk,
                "status": "deduped",
                "accepted_or_rejected_reason": "duplicate_dedupe_key",
            }
        )
        _append_entry(ingest_registry_path, base)
        return base

    base.update(
        {
            "normalized_trigger_type": nt,
            "normalized_payload": norm.get("normalized_payload"),
            "dedupe_key": dk,
            "status": "accepted",
            "accepted_or_rejected_reason": "accepted_governed",
        }
    )
    _append_entry(ingest_registry_path, base)
    return base


def _append_entry(path: Path, entry: dict[str, Any]) -> None:
    reg = load_ingest_registry(path)
    rows = list(reg.get("entries") or [])
    rows.append(entry)
    reg["entries"] = rows
    save_ingest_registry(path, reg)


def accepted_entries_pending_cycle(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    reg = load_ingest_registry(path)
    for e in reg.get("entries") or []:
        if e.get("status") == "accepted" and not e.get("linked_cycle_id"):
            out.append(e)
    return out


def entry_to_supplemental_trigger(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry.get("status") != "accepted" or entry.get("linked_cycle_id"):
        return None
    nt = str(entry.get("normalized_trigger_type") or "")
    dk = str(entry.get("dedupe_key") or "")
    pay = entry.get("normalized_payload") or {}
    eid = str(entry.get("event_id") or "")
    if not nt or not dk:
        return None
    if nt == "named_source_signal":
        note = str(pay.get("note") or "")
        return {
            "trigger_type": "named_source_signal",
            "dedupe_key": dk,
            "priority": 30,
            "payload": {"founder_note_excerpt": note[:500], "external_normalized": pay},
            "suggested_job_type": "debate.execute",
            "external_event_id": eid,
        }
    if nt == "manual_watchlist":
        jt = str(pay.get("suggested_job_type") or "debate.execute")
        if jt not in JOB_TYPES:
            jt = "evidence.refresh"
        return {
            "trigger_type": "manual_watchlist",
            "dedupe_key": dk,
            "priority": 15,
            "payload": {
                "asset_id": pay.get("asset_id"),
                "note": pay.get("note", ""),
                "suggested_job_type": jt,
            },
            "suggested_job_type": jt,
            "external_event_id": eid,
            "manual_file": None,
        }
    if nt == "operator_research_signal":
        return {
            "trigger_type": "operator_research_signal",
            "dedupe_key": dk,
            "priority": 20,
            "payload": {
                "decision": {
                    "timestamp": entry.get("received_at"),
                    "asset_id": (entry.get("asset_scope") or {}).get("asset_id"),
                    "decision_type": "watch",
                    "founder_note": pay.get("summary", ""),
                    "linked_message_summary": "external_ingest",
                    "linked_authoritative_artifact": pay.get("artifact_ref", ""),
                    "linked_research_provenance": "external_ingest",
                }
            },
            "suggested_job_type": "hypothesis.check",
            "external_event_id": eid,
        }
    if nt == "closeout_reopen_candidate":
        return {
            "trigger_type": "closeout_reopen_candidate",
            "dedupe_key": dk,
            "priority": 25,
            "payload": {
                "decision": {
                    "timestamp": entry.get("received_at"),
                    "asset_id": (entry.get("asset_scope") or {}).get("asset_id"),
                    "decision_type": "reopen_request",
                    "founder_note": pay.get("rationale", ""),
                    "linked_message_summary": "external_ingest",
                    "linked_authoritative_artifact": "",
                    "linked_research_provenance": "external_ingest",
                }
            },
            "suggested_job_type": "debate.execute",
            "external_event_id": eid,
        }
    if nt == "changed_artifact_bundle":
        return {
            "trigger_type": "changed_artifact_bundle",
            "dedupe_key": dk,
            "priority": 10,
            "payload": {"phase46_generated_utc": pay.get("hint", "external"), "external": True},
            "suggested_job_type": "evidence.refresh",
            "external_event_id": eid,
        }
    return None


def supplemental_triggers_from_registry(path: Path) -> list[dict[str, Any]]:
    sup: list[dict[str, Any]] = []
    for e in accepted_entries_pending_cycle(path):
        t = entry_to_supplemental_trigger(e)
        if t:
            sup.append(t)
    return sup
