"""Patch 12 — ``/api/events`` and ``/api/events/batch`` JSON routes.

These handlers are thin wrappers around ``TelemetryIngestor``. ``dispatch_json``
has already validated the Bearer token + allowlist + attached the caller's
``user_id`` via ``AuthDecision``.
"""

from __future__ import annotations

from typing import Any, Optional

from phase47_runtime.auth.guard import AuthDecision
from phase47_runtime.telemetry.ingest import IngestDecision, TelemetryIngestor


def _user_id_or_unauthed(decision: Optional[AuthDecision]) -> Optional[str]:
    if decision is None or not decision.ok:
        return None
    return decision.user_id or None


def api_events_post(
    raw: dict[str, Any],
    *,
    decision: Optional[AuthDecision],
    ingestor: Optional[TelemetryIngestor] = None,
) -> tuple[int, dict[str, Any]]:
    user_id = _user_id_or_unauthed(decision)
    if not user_id:
        return 401, {"ok": False, "error": "auth_required", "contract": "EVENT_V1"}
    ing = ingestor or TelemetryIngestor()
    d: IngestDecision = ing.ingest(raw if isinstance(raw, dict) else {}, user_id=user_id)
    return d.http_status, d.to_response()


def api_events_batch_post(
    raw: dict[str, Any],
    *,
    decision: Optional[AuthDecision],
    ingestor: Optional[TelemetryIngestor] = None,
) -> tuple[int, dict[str, Any]]:
    user_id = _user_id_or_unauthed(decision)
    if not user_id:
        return 401, {"ok": False, "error": "auth_required", "contract": "EVENT_V1"}
    ing = ingestor or TelemetryIngestor()
    d, accepted = ing.ingest_batch(raw if isinstance(raw, dict) else {}, user_id=user_id)
    if not d.ok:
        return d.http_status, d.to_response()
    return 200, {
        "ok": True,
        "stored": d.stored,
        "accepted_count": len(accepted),
        "contract": "EVENT_V1",
    }


__all__ = ["api_events_post", "api_events_batch_post"]
