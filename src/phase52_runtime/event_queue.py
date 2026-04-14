"""Bounded persistent queue for accepted events (optional pre-registry path)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_event_queue_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_event_queue_v1.json"


def load_queue(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "max_depth": 500, "items": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "max_depth": 500, "items": []}


def save_queue(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def pending_dedupe_keys(data: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for it in data.get("items") or []:
        if it.get("status") == "pending":
            dk = str(it.get("dedupe_key") or "")
            if dk:
                out.add(dk)
    return out


def enqueue_event(
    *,
    path: Path,
    body: dict[str, Any],
    dedupe_key: str,
    source_id: str,
    max_depth: int | None = None,
) -> dict[str, Any]:
    data = load_queue(path)
    md = int(max_depth or data.get("max_depth") or 500)
    items = [x for x in (data.get("items") or []) if isinstance(x, dict)]
    pending = [x for x in items if x.get("status") == "pending"]
    if len(pending) >= md:
        return {"ok": False, "reason": "queue_full", "max_depth": md}
    if dedupe_key and dedupe_key in pending_dedupe_keys(data):
        return {"ok": False, "reason": "duplicate_pending_dedupe_key", "dedupe_key": dedupe_key}
    row = {
        "queue_id": str(uuid.uuid4()),
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "dedupe_key": dedupe_key,
        "source_id": source_id,
        "status": "pending",
        "body": body,
    }
    items.append(row)
    data["items"] = items
    data["max_depth"] = md
    save_queue(path, data)
    return {"ok": True, "queue_id": row["queue_id"], "queue_depth_pending": len(pending) + 1}


def pop_next_pending(path: Path) -> dict[str, Any] | None:
    data = load_queue(path)
    items = list(data.get("items") or [])
    for i, it in enumerate(items):
        if it.get("status") == "pending":
            it["status"] = "dequeued"
            it["dequeued_at"] = datetime.now(timezone.utc).isoformat()
            items[i] = it
            data["items"] = items
            save_queue(path, data)
            return it
    return None


def mark_queue_item_consumed(path: Path, queue_id: str) -> None:
    mark_queue_item_status(path, queue_id, "consumed")


def mark_queue_item_status(path: Path, queue_id: str, status: str) -> None:
    data = load_queue(path)
    items = list(data.get("items") or [])
    for i, it in enumerate(items):
        if str(it.get("queue_id")) == queue_id:
            it["status"] = status
            it["closed_at"] = datetime.now(timezone.utc).isoformat()
            items[i] = it
            break
    data["items"] = items
    save_queue(path, data)


def queue_depth_pending(path: Path) -> int:
    data = load_queue(path)
    return sum(1 for x in (data.get("items") or []) if x.get("status") == "pending")


def prune_queue_to_bound(path: Path, *, max_items_total: int = 2000) -> None:
    """Drop oldest consumed rows if list grows too long."""
    data = load_queue(path)
    items = [x for x in (data.get("items") or []) if isinstance(x, dict)]
    if len(items) <= max_items_total:
        return
    consumed = [x for x in items if x.get("status") == "consumed"]
    pending = [x for x in items if x.get("status") != "consumed"]
    drop = len(items) - max_items_total
    if drop > 0 and consumed:
        consumed = consumed[drop:]
    data["items"] = pending + consumed
    save_queue(path, data)
