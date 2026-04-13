"""In-process notification events for UI polling; future Slack/email/webhook attachment points."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_MAX = 200
_lock = Lock()
_events: deque[dict[str, Any]] = deque(maxlen=_MAX)


def emit_notification(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    ev = {
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "payload": payload,
    }
    with _lock:
        _events.append(ev)
    return ev


def list_notifications(*, limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return list(_events)[-limit:]


def clear_notifications_for_tests() -> None:
    with _lock:
        _events.clear()
