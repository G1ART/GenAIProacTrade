"""Durable dead-letter registry for failed governed ingress."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_dead_letter_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_dead_letter_v1.json"


def load_dead_letter(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "entries": []}


def save_dead_letter(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _excerpt(raw_body: bytes | None, body_dict: dict[str, Any] | None, max_len: int = 2048) -> str:
    if raw_body:
        try:
            s = raw_body.decode("utf-8", errors="replace")
        except Exception:
            s = repr(raw_body[:200])
        return s[:max_len]
    return json.dumps(body_dict or {}, ensure_ascii=False)[:max_len]


def append_dead_letter(
    path: Path,
    *,
    source_id: str,
    raw_event_type: str | None,
    normalized_trigger_type: str | None,
    failure_stage: str,
    failure_reason: str,
    raw_body: bytes | None,
    body_dict: dict[str, Any] | None,
    dedupe_key: str | None,
    replayable: bool,
    extra: dict[str, Any] | None = None,
) -> str:
    dl_id = str(uuid.uuid4())
    row: dict[str, Any] = {
        "dead_letter_id": dl_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source_id": str(source_id or ""),
        "raw_event_type": raw_event_type,
        "normalized_trigger_type": normalized_trigger_type,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "raw_body_excerpt": _excerpt(raw_body, body_dict),
        "dedupe_key": dedupe_key,
        "replayable": bool(replayable),
        "replay_status": "none",
        "linked_replay_event_id": None,
    }
    if raw_body:
        row["payload_sha256"] = hashlib.sha256(raw_body).hexdigest()
    if extra:
        row.update(extra)
    data = load_dead_letter(path)
    data.setdefault("entries", []).append(row)
    save_dead_letter(path, data)
    return dl_id


def list_dead_letters(path: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    data = load_dead_letter(path)
    entries = list(data.get("entries") or [])
    return list(reversed(entries[-limit:]))


def get_dead_letter(path: Path, dead_letter_id: str) -> dict[str, Any] | None:
    for e in load_dead_letter(path).get("entries") or []:
        if str(e.get("dead_letter_id")) == str(dead_letter_id):
            return e
    return None


def mark_replay_attempted(path: Path, dead_letter_id: str, *, linked_event_id: str | None, status: str) -> bool:
    data = load_dead_letter(path)
    changed = False
    for e in data.get("entries") or []:
        if str(e.get("dead_letter_id")) == str(dead_letter_id):
            e["replay_status"] = status
            e["last_replay_at"] = datetime.now(timezone.utc).isoformat()
            if linked_event_id:
                e["linked_replay_event_id"] = linked_event_id
            changed = True
            break
    if changed:
        save_dead_letter(path, data)
    return changed


def dead_letter_counts_by_stage(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in load_dead_letter(path).get("entries") or []:
        st = str(e.get("failure_stage") or "unknown")
        out[st] = out.get(st, 0) + 1
    return out
