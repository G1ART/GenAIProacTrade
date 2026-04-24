"""Patch 12 — invite-only beta allowlist check.

Resolves a Supabase user id against ``beta_users_v1`` and returns an
actionable status plus role. The guard layer converts the status into an
HTTP code; this module only cares about correctness + caching.

Modes (env ``METIS_BETA_ALLOWLIST_MODE``):

* ``enforce`` (default when SUPABASE_URL + SERVICE_ROLE_KEY are set):
  requires a row and ``status in {invited, active}`` to proceed.
* ``off``: every authenticated user passes (useful for local dev / ``.env``
  missing).
* ``shadow``: log-only; always passes but records a hint in the decision.

The module keeps a tiny 30s per-user cache so rapid bursts from a single
client don't hammer PostgREST. Cache is global but bounded; revocations
propagate within one TTL window.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Optional

from phase47_runtime.auth.supabase_rest import SupabaseRestClient, SupabaseRestError


ALLOWLIST_MODE_ENFORCE = "enforce"
ALLOWLIST_MODE_SHADOW = "shadow"
ALLOWLIST_MODE_OFF = "off"
_ALLOWED_MODES = frozenset({ALLOWLIST_MODE_ENFORCE, ALLOWLIST_MODE_SHADOW, ALLOWLIST_MODE_OFF})

_PASSING_STATUSES = frozenset({"invited", "active"})
_BLOCKING_STATUSES = frozenset({"paused", "revoked"})

_CACHE_TTL_SECONDS = 30.0
_CACHE_MAX_ENTRIES = 512


@dataclass(frozen=True)
class BetaAllowlistResult:
    ok: bool
    user_id: str
    status: str
    role: str
    mode: str
    reason: Optional[str] = None


class _BetaAllowlistCache:
    """Thread-safe TTL cache for ``(user_id) -> (expires_at, result)``."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: dict[str, tuple[float, BetaAllowlistResult]] = {}

    def get(self, user_id: str, *, now_epoch: float) -> Optional[BetaAllowlistResult]:
        with self._lock:
            entry = self._entries.get(user_id)
            if entry is None:
                return None
            expires_at, result = entry
            if expires_at < now_epoch:
                self._entries.pop(user_id, None)
                return None
            return result

    def set(self, user_id: str, result: BetaAllowlistResult, *, now_epoch: float) -> None:
        with self._lock:
            if len(self._entries) >= _CACHE_MAX_ENTRIES:
                # drop the oldest half — good enough for a private beta.
                for k in list(self._entries.keys())[: _CACHE_MAX_ENTRIES // 2]:
                    self._entries.pop(k, None)
            self._entries[user_id] = (now_epoch + _CACHE_TTL_SECONDS, result)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_CACHE = _BetaAllowlistCache()


def _resolve_mode() -> str:
    raw = (os.environ.get("METIS_BETA_ALLOWLIST_MODE") or "").strip().lower()
    if raw in _ALLOWED_MODES:
        return raw
    # default: enforce iff the service role is wired up
    url_ok = bool((os.environ.get("SUPABASE_URL") or "").strip())
    key_ok = bool((os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip())
    return ALLOWLIST_MODE_ENFORCE if (url_ok and key_ok) else ALLOWLIST_MODE_OFF


def clear_allowlist_cache() -> None:
    """Test hook — dropped after each test that monkeypatches mode/env."""

    _CACHE.clear()


def _build_rest_client() -> Optional[SupabaseRestClient]:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return None
    return SupabaseRestClient(url=url, service_role_key=key)


def verify_user_is_active_beta(
    user_id: str,
    *,
    client: Optional[SupabaseRestClient] = None,
    now_epoch: Optional[float] = None,
    mode_override: Optional[str] = None,
) -> BetaAllowlistResult:
    """Return an allowlist decision for ``user_id``.

    Parameters
    ----------
    user_id: Supabase ``auth.users.id``, already verified by JWT.
    client: optional injected REST client (tests).
    now_epoch: optional ``time.time()`` override (tests).
    mode_override: optional env override (tests).
    """

    uid = (user_id or "").strip()
    mode = (mode_override or _resolve_mode()).strip().lower() or ALLOWLIST_MODE_OFF
    if not uid:
        return BetaAllowlistResult(
            ok=False, user_id="", status="unknown", role="beta_user", mode=mode, reason="empty_user_id"
        )

    if mode == ALLOWLIST_MODE_OFF:
        return BetaAllowlistResult(
            ok=True, user_id=uid, status="unknown", role="beta_user", mode=mode, reason=None
        )

    now = now_epoch if now_epoch is not None else time.time()
    cached = _CACHE.get(uid, now_epoch=now)
    if cached is not None:
        return cached

    rest_client = client or _build_rest_client()
    if rest_client is None:
        result = BetaAllowlistResult(
            ok=False,
            user_id=uid,
            status="unknown",
            role="beta_user",
            mode=mode,
            reason="supabase_not_configured",
        )
        _CACHE.set(uid, result, now_epoch=now)
        return result

    try:
        rows = rest_client.select(
            "beta_users_v1",
            columns="user_id,status,role",
            filters={"user_id": f"eq.{uid}", "limit": "1"},
        )
    except SupabaseRestError:
        # Fail closed in enforce mode, fail open in shadow mode.
        if mode == ALLOWLIST_MODE_SHADOW:
            return BetaAllowlistResult(
                ok=True,
                user_id=uid,
                status="unknown",
                role="beta_user",
                mode=mode,
                reason="lookup_failed_shadow_pass",
            )
        result = BetaAllowlistResult(
            ok=False,
            user_id=uid,
            status="unknown",
            role="beta_user",
            mode=mode,
            reason="allowlist_lookup_failed",
        )
        _CACHE.set(uid, result, now_epoch=now)
        return result

    if not rows:
        if mode == ALLOWLIST_MODE_SHADOW:
            return BetaAllowlistResult(
                ok=True,
                user_id=uid,
                status="unknown",
                role="beta_user",
                mode=mode,
                reason="no_row_shadow_pass",
            )
        result = BetaAllowlistResult(
            ok=False,
            user_id=uid,
            status="unknown",
            role="beta_user",
            mode=mode,
            reason="not_on_allowlist",
        )
        _CACHE.set(uid, result, now_epoch=now)
        return result

    row: dict[str, Any] = rows[0]
    status = str(row.get("status") or "unknown")
    role = str(row.get("role") or "beta_user")

    if status in _PASSING_STATUSES:
        result = BetaAllowlistResult(ok=True, user_id=uid, status=status, role=role, mode=mode, reason=None)
    elif status in _BLOCKING_STATUSES:
        reason = "allowlist_revoked" if status == "revoked" else "allowlist_paused"
        result = BetaAllowlistResult(ok=False, user_id=uid, status=status, role=role, mode=mode, reason=reason)
    else:
        result = BetaAllowlistResult(
            ok=False, user_id=uid, status=status, role=role, mode=mode, reason="allowlist_unknown_status"
        )
    _CACHE.set(uid, result, now_epoch=now)
    return result


__all__ = [
    "ALLOWLIST_MODE_ENFORCE",
    "ALLOWLIST_MODE_SHADOW",
    "ALLOWLIST_MODE_OFF",
    "BetaAllowlistResult",
    "clear_allowlist_cache",
    "verify_user_is_active_beta",
]
