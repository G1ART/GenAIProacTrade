"""Single active cycle lease — overlap protection across scheduler invocations."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_TTL_SECONDS = 900


def default_lease_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "cycle_lease_v1.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def is_lease_stale(entry: dict[str, Any]) -> bool:
    exp = _parse_iso(str(entry.get("expires_at") or ""))
    if exp is None:
        return True
    return _now() >= exp


def read_lease(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return None


def try_acquire_lease(
    path: Path,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    holder_hint: str | None = None,
) -> dict[str, Any]:
    """Return {ok, cycle_id, reason, lease_record?}. Non-destructive read before write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_lease(path)
    if existing and existing.get("status") == "active" and not is_lease_stale(existing):
        return {
            "ok": False,
            "reason": "lease_held_by_other_holder",
            "holder": existing.get("holder"),
            "expires_at": existing.get("expires_at"),
        }
    cycle_id = str(uuid.uuid4())
    holder = holder_hint or f"pid_{os.getpid()}"
    now = _now()
    rec = {
        "schema_version": 1,
        "status": "active",
        "cycle_id": cycle_id,
        "holder": holder,
        "acquired_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=max(30, int(ttl_seconds)))).isoformat(),
    }
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "cycle_id": cycle_id, "reason": "acquired", "lease_record": rec}


def release_lease(path: Path, *, cycle_id: str | None = None) -> None:
    cur = read_lease(path)
    if not cur:
        return
    if cycle_id and str(cur.get("cycle_id") or "") != cycle_id:
        return
    cur["status"] = "released"
    cur["released_at"] = _now().isoformat()
    path.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")


def lease_behavior_doc() -> dict[str, Any]:
    return {
        "ttl_seconds_default": DEFAULT_TTL_SECONDS,
        "semantics": "At most one active non-stale lease; acquire fails if another holder holds it.",
        "stale_rule": "expires_at in the past allows a new acquire",
        "safe_failure": "Skip cycle with audit entry; do not run Phase 48",
    }
