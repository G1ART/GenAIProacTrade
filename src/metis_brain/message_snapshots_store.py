"""Append-only message snapshot store for Replay ↔ Today linkage (Product Spec §5.3, §6.4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1
_MAX_SNAPSHOTS = 400


def message_snapshots_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mvp" / "message_snapshots_v0.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": _SCHEMA_VERSION, "snapshots": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": _SCHEMA_VERSION, "snapshots": {}}
    if not isinstance(raw, dict):
        return {"schema_version": _SCHEMA_VERSION, "snapshots": {}}
    snaps = raw.get("snapshots")
    if not isinstance(snaps, dict):
        snaps = {}
    return {"schema_version": int(raw.get("schema_version") or _SCHEMA_VERSION), "snapshots": snaps}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def upsert_message_snapshot(repo_root: Path, snapshot_id: str, record: dict[str, Any]) -> None:
    """Store or replace one snapshot (trim oldest when over cap)."""
    sid = (snapshot_id or "").strip()
    if not sid:
        return
    p = message_snapshots_path(repo_root)
    data = _load(p)
    snaps: dict[str, Any] = data["snapshots"]
    rec = {**record, "stored_at_utc": datetime.now(timezone.utc).isoformat()}
    snaps[sid] = rec
    while len(snaps) > _MAX_SNAPSHOTS:
        oldest_key = min(
            snaps.keys(),
            key=lambda k: str((snaps.get(k) or {}).get("stored_at_utc") or "1970-01-01T00:00:00+00:00"),
        )
        snaps.pop(oldest_key, None)
    _save(p, data)


def get_message_snapshot(repo_root: Path, snapshot_id: str) -> dict[str, Any] | None:
    sid = (snapshot_id or "").strip()
    if not sid:
        return None
    raw = _load(message_snapshots_path(repo_root))["snapshots"].get(sid)
    return raw if isinstance(raw, dict) else None
