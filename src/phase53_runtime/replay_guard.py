"""Persistent replay / nonce guard for signed ingress."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def default_replay_guard_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_replay_guard_v1.json"


def load_replay_guard(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "entries": []}


def save_replay_guard(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _prune(data: dict[str, Any], *, now: datetime) -> None:
    entries = [e for e in (data.get("entries") or []) if _parse_expiry(e.get("expires_at"), now=now)]
    data["entries"] = entries


def _parse_expiry(expires_at: str | None, *, now: datetime) -> bool:
    if not expires_at:
        return False
    try:
        s = str(expires_at).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s) > now
    except ValueError:
        return False


def try_register_nonce(
    path: Path,
    *,
    source_id: str,
    nonce: str,
    signature_digest: str,
    now: datetime | None = None,
    ttl_seconds: int = 900,
) -> tuple[bool, str]:
    """
    Returns (allowed, reason). If allowed, persists entry.
    Blocks duplicate (source_id, nonce) or duplicate signature_digest while TTL valid.
    """
    now = now or datetime.now(timezone.utc)
    data = load_replay_guard(path)
    _prune(data, now=now)
    sid = str(source_id or "").strip()
    n = str(nonce or "").strip()
    sigd = str(signature_digest or "").strip().lower()
    if not sid or not n:
        return False, "missing_nonce_or_source"

    for e in data.get("entries") or []:
        if str(e.get("source_id")) == sid and str(e.get("nonce")) == n:
            return False, "nonce_replay"
        if sigd and str(e.get("signature_digest") or "").lower() == sigd:
            return False, "signature_tuple_replay"

    exp = (now + timedelta(seconds=ttl_seconds)).isoformat()
    row = {
        "guard_id": str(uuid.uuid4()),
        "source_id": sid,
        "nonce": n,
        "signature_digest": sigd,
        "first_seen_at": now.isoformat(),
        "expires_at": exp,
    }
    data.setdefault("entries", []).append(row)
    save_replay_guard(path, data)
    return True, "ok"


def replay_guard_count(path: Path) -> int:
    data = load_replay_guard(path)
    return len(data.get("entries") or [])
