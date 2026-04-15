"""Bounded operator replay from dead-letter into governed ingress."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase52_runtime.governed_ingress import process_governed_external_ingest

from phase53_runtime.dead_letter_registry import default_dead_letter_path, get_dead_letter, mark_replay_attempted


def replay_dead_letter_entry(
    dead_letter_id: str,
    *,
    repo_root: Path,
    webhook_secret: str,
    dead_letter_path: Path | None = None,
    source_registry_path: Path | None = None,
    budget_state_path: Path | None = None,
    queue_path: Path | None = None,
    ingest_registry_path: Path | None = None,
    audit_path: Path | None = None,
    control_plane_path: Path | None = None,
    replay_guard_path: Path | None = None,
    raw_body_override: bytes | None = None,
) -> dict[str, Any]:
    """
    Replays stored excerpt as JSON body when full raw not stored.
    Still passes current governed gates (not force-accept).
    """
    dlp = dead_letter_path or default_dead_letter_path(repo_root)
    ent = get_dead_letter(dlp, dead_letter_id)
    if not ent:
        return {"ok": False, "error": "dead_letter_not_found"}
    if not ent.get("replayable"):
        return {"ok": False, "error": "not_replayable"}
    if str(ent.get("replay_status") or "") in ("replayed_ok", "replayed_failed_max"):
        return {"ok": False, "error": "replay_already_attempted", "replay_status": ent.get("replay_status")}

    body: dict[str, Any]
    raw: bytes
    if raw_body_override is not None:
        raw = raw_body_override
        body = json.loads(raw.decode("utf-8"))
    else:
        try:
            body = json.loads(str(ent.get("raw_body_excerpt") or "{}"))
        except json.JSONDecodeError:
            return {"ok": False, "error": "invalid_stored_body_excerpt"}
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    sid = str(ent.get("source_id") or "")
    mark_replay_attempted(dlp, dead_letter_id, linked_event_id=None, status="replay_in_progress")

    out = process_governed_external_ingest(
        body,
        source_id_header=sid,
        webhook_secret=webhook_secret,
        repo_root=repo_root,
        source_registry_path=source_registry_path,
        budget_state_path=budget_state_path,
        queue_path=queue_path,
        ingest_registry_path=ingest_registry_path,
        audit_path=audit_path,
        control_plane_path=control_plane_path,
        raw_body=raw,
        http_headers={},
        replay_guard_path=replay_guard_path,
        dead_letter_path=dlp,
        operator_replay_dead_letter_id=dead_letter_id,
    )
    if out.get("ok"):
        mark_replay_attempted(
            dlp,
            dead_letter_id,
            linked_event_id=str((out.get("registry_entry") or {}).get("event_id") or ""),
            status="replayed_ok",
        )
    else:
        mark_replay_attempted(dlp, dead_letter_id, linked_event_id=None, status="replayed_failed")
    return {**out, "dead_letter_id": dead_letter_id}
