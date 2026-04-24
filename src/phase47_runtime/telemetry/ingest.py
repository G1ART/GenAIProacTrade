"""Patch 12 — telemetry ingest (sanitize + rate limit + service-role insert).

Flow:
1. ``/api/events`` (handled by ``routes_events.py``) calls ``TelemetryIngestor.ingest`` /
   ``.ingest_batch`` after the auth guard has attached the caller's ``user_id``.
2. ``sanitize_event`` validates the allowlist, coerces types, drops unknown
   fields, bounds metadata size, and rejects bad session UUIDs.
3. A sliding-window in-memory rate limiter (100/min/user) protects PostgREST
   from pathological client behaviour.
4. If Supabase is configured + ``METIS_TELEMETRY_ENABLED!=0``, the event is
   POSTed to ``product_usage_events_v1`` via the service role REST client.
   Otherwise the sanitised payload is returned with ``stored=False``
   (useful for local dev + tests).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Optional

from phase47_runtime.auth.supabase_rest import SupabaseRestClient, SupabaseRestError
from phase47_runtime.telemetry.event_taxonomy import (
    ALLOWED_HORIZON_KEYS,
    ALLOWED_LANGS,
    ALLOWED_SURFACES,
    EVENT_TAXONOMY_V1,
    MAX_METADATA_BYTES,
)


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Fields we accept in the metadata object (bounded surface).
_METADATA_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"intent", "len", "source", "variant", "fallback", "dedupe_key"}
)


@dataclass(frozen=True)
class IngestDecision:
    ok: bool
    http_status: int
    reason: Optional[str]
    stored: bool
    event: Optional[dict[str, Any]]

    def to_response(self) -> dict[str, Any]:
        if self.ok:
            return {"ok": True, "stored": self.stored, "contract": "EVENT_V1"}
        return {
            "ok": False,
            "error": "event_rejected",
            "reason": self.reason or "unknown",
            "contract": "EVENT_V1",
        }


def _clean_string(value: Any, *, max_len: int = 128) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_len]


def sanitize_event(
    body: dict[str, Any],
    *,
    user_id: str,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """Validate + coerce a raw event. Returns ``(ok, reason, event_row)``."""

    if not isinstance(body, dict):
        return False, "invalid_body", None

    event_name = _clean_string(body.get("event_name"), max_len=64)
    if not event_name or event_name not in EVENT_TAXONOMY_V1:
        return False, "event_name_not_allowlisted", None

    session_id = _clean_string(body.get("session_id"), max_len=64) or ""
    if not _UUID_RE.match(session_id):
        return False, "invalid_session_id", None

    surface = _clean_string(body.get("surface"), max_len=32) or ""
    if surface not in ALLOWED_SURFACES:
        return False, "surface_not_allowlisted", None

    horizon_raw = _clean_string(body.get("horizon_key"), max_len=32)
    if horizon_raw is not None and horizon_raw not in ALLOWED_HORIZON_KEYS:
        return False, "invalid_horizon_key", None

    lang_raw = _clean_string(body.get("lang"), max_len=8)
    if lang_raw is not None:
        lang_raw = lang_raw.lower()
        if lang_raw not in ALLOWED_LANGS:
            return False, "invalid_lang", None

    metadata_raw = body.get("metadata")
    metadata: dict[str, Any] = {}
    if isinstance(metadata_raw, dict):
        for k, v in metadata_raw.items():
            if k not in _METADATA_ALLOWED_KEYS:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                if isinstance(v, str):
                    metadata[k] = v[:256]
                else:
                    metadata[k] = v
        try:
            encoded = json.dumps(metadata, ensure_ascii=False)
        except (TypeError, ValueError):
            return False, "invalid_metadata", None
        if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
            return False, "metadata_too_large", None
    elif metadata_raw is not None:
        return False, "invalid_metadata", None

    event_row: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "event_name": event_name,
        "surface": surface,
        "route": _clean_string(body.get("route"), max_len=256),
        "asset_id": _clean_string(body.get("asset_id"), max_len=32),
        "horizon_key": horizon_raw,
        "result_state": _clean_string(body.get("result_state"), max_len=64),
        "lang": lang_raw,
        "metadata": metadata,
    }
    return True, None, event_row


@dataclass
class RateLimiter:
    """Sliding-window in-memory rate limiter keyed by user id.

    Default: 100 events / 60 seconds / user. Good enough for the private
    beta (single Railway web dyno); Redis can replace this if we scale.
    """

    max_events: int = 100
    window_seconds: float = 60.0
    _lock: RLock = field(default_factory=RLock)
    _windows: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, user_id: str, *, now_epoch: Optional[float] = None) -> bool:
        now = now_epoch if now_epoch is not None else time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._windows.get(user_id)
            if q is None:
                q = deque()
                self._windows[user_id] = q
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_events:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


class TelemetryIngestor:
    """Small façade used by ``routes_events.py``. Uses a module-level singleton
    rate limiter + an injected Supabase REST client (so tests can stub)."""

    BATCH_MAX = 50

    def __init__(
        self,
        *,
        rest_client: Optional[SupabaseRestClient] = None,
        rate_limiter: Optional[RateLimiter] = None,
        telemetry_enabled: Optional[bool] = None,
    ) -> None:
        self._rest_client = rest_client
        self._rate_limiter = rate_limiter or _DEFAULT_RATE_LIMITER
        if telemetry_enabled is None:
            flag = (os.environ.get("METIS_TELEMETRY_ENABLED") or "").strip().lower()
            self._telemetry_enabled = flag not in ("0", "false", "no", "off")
        else:
            self._telemetry_enabled = bool(telemetry_enabled)

    def _client(self) -> Optional[SupabaseRestClient]:
        if self._rest_client is not None:
            return self._rest_client
        url = (os.environ.get("SUPABASE_URL") or "").strip()
        key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            return None
        return SupabaseRestClient(url=url, service_role_key=key)

    def _store(self, rows: list[dict[str, Any]]) -> bool:
        if not self._telemetry_enabled or not rows:
            return False
        client = self._client()
        if client is None:
            return False
        try:
            client.insert("product_usage_events_v1", rows, return_representation=False)
            return True
        except SupabaseRestError:
            return False

    def ingest(self, body: dict[str, Any], *, user_id: str) -> IngestDecision:
        ok, reason, event_row = sanitize_event(body, user_id=user_id)
        if not ok or event_row is None:
            return IngestDecision(
                ok=False, http_status=400, reason=reason, stored=False, event=None
            )
        if not self._rate_limiter.allow(user_id):
            return IngestDecision(
                ok=False, http_status=429, reason="rate_limited", stored=False, event=event_row
            )
        stored = self._store([event_row])
        return IngestDecision(ok=True, http_status=200, reason=None, stored=stored, event=event_row)

    def ingest_batch(
        self, body: dict[str, Any], *, user_id: str
    ) -> tuple[IngestDecision, list[dict[str, Any]]]:
        if not isinstance(body, dict):
            return IngestDecision(False, 400, "invalid_body", False, None), []
        events_raw = body.get("events")
        if not isinstance(events_raw, list) or not events_raw:
            return IngestDecision(False, 400, "events_required", False, None), []
        if len(events_raw) > self.BATCH_MAX:
            return IngestDecision(False, 400, "batch_too_large", False, None), []

        sanitized: list[dict[str, Any]] = []
        for item in events_raw:
            ok, reason, event_row = sanitize_event(item if isinstance(item, dict) else {}, user_id=user_id)
            if not ok or event_row is None:
                return (
                    IngestDecision(False, 400, reason or "event_rejected", False, None),
                    [],
                )
            sanitized.append(event_row)

        for _row in sanitized:
            if not self._rate_limiter.allow(user_id):
                return (
                    IngestDecision(False, 429, "rate_limited", False, None),
                    [],
                )
        stored = self._store(sanitized)
        return (
            IngestDecision(True, 200, None, stored, sanitized[0] if sanitized else None),
            sanitized,
        )


_DEFAULT_RATE_LIMITER = RateLimiter()


def reset_default_rate_limiter() -> None:
    """Test hook."""

    _DEFAULT_RATE_LIMITER.reset()


__all__ = [
    "IngestDecision",
    "RateLimiter",
    "TelemetryIngestor",
    "reset_default_rate_limiter",
    "sanitize_event",
]
