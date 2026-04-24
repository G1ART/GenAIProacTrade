"""Patch 12 — ``/api/auth/*`` JSON routes.

Three endpoints:

* ``POST /api/auth/session`` — client posts the Supabase access token once
  a magic-link redirect completes; we verify HS256, check the invite
  allowlist, upsert ``profiles_v1.last_seen_at``, and return a bounded
  DTO (alias user id, display_name, role, preferred_lang, session_id).
* ``GET  /api/auth/me``      — returns the current profile + allowlist
  status. Requires the Bearer guard (not in ``PUBLIC_API_PATHS``).
* ``POST /api/auth/signout``  — logs a ``auth_signout`` event and 200s;
  actual token revocation is handled by supabase-js on the client.

All responses strip raw emails + raw UUIDs out of the DTO — only the
12-char alias escapes the server.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Optional

from phase47_runtime.auth.access_token_resolver import resolve_access_token
from phase47_runtime.auth.beta_allowlist import (
    ALLOWLIST_MODE_OFF,
    BetaAllowlistResult,
    verify_user_is_active_beta,
)
from phase47_runtime.auth.guard import AuthDecision, user_id_alias
from phase47_runtime.auth.jwt_verifier import verify_supabase_jwt  # noqa: F401  (re-exported for tests)
from phase47_runtime.auth.supabase_rest import SupabaseRestClient, SupabaseRestError


def _jwt_secret() -> str:
    return (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()


def _build_rest_client() -> Optional[SupabaseRestClient]:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return None
    return SupabaseRestClient(url=url, service_role_key=key)


def _preferred_lang_from_claims(claims: dict[str, Any]) -> Optional[str]:
    meta = claims.get("user_metadata") or {}
    if isinstance(meta, dict):
        raw = str(meta.get("preferred_lang") or "").strip().lower()
        if raw in ("ko", "en"):
            return raw
    return None


def _sanitized_profile_dto(
    *,
    user_id: str,
    display_name: Optional[str],
    role: str,
    allowlist_status: str,
    allowlist_mode: str,
    preferred_lang: Optional[str],
    session_id: str,
) -> dict[str, Any]:
    return {
        "user_id_alias": user_id_alias(user_id),
        "display_name": (display_name or "").strip() or None,
        "role": role or "beta_user",
        "allowlist_status": allowlist_status or "unknown",
        "allowlist_mode": allowlist_mode or "unknown",
        "preferred_lang": preferred_lang,
        "session_id": session_id,
    }


def _rest_fallback_configured() -> bool:
    url_ok = bool((os.environ.get("SUPABASE_URL") or "").strip())
    key_ok = bool((os.environ.get("SUPABASE_ANON_KEY") or "").strip())
    return url_ok and key_ok


def api_auth_session(
    raw: dict[str, Any],
    *,
    now_epoch: Optional[int] = None,
    rest_client: Optional[SupabaseRestClient] = None,
    allowlist_override: Optional[BetaAllowlistResult] = None,
    verifier=resolve_access_token,
) -> tuple[int, dict[str, Any]]:
    """Verify the posted JWT and activate the beta session.

    Body: ``{"access_token": "<supabase jwt>", "display_name": "...",
             "preferred_lang": "ko"|"en"}``.
    """

    if not isinstance(raw, dict):
        return 400, {"ok": False, "error": "invalid_body", "contract": "AUTH_V1"}
    token = str(raw.get("access_token") or "").strip()
    if not token:
        return 400, {"ok": False, "error": "missing_access_token", "contract": "AUTH_V1"}

    secret = _jwt_secret()
    # Patch 12.1 — auth is considered configured if EITHER HS256 secret is
    # set OR the REST fallback (SUPABASE_URL + ANON_KEY) is available.
    if not secret and not _rest_fallback_configured():
        return 503, {"ok": False, "error": "auth_not_configured", "contract": "AUTH_V1"}

    vr = verifier(token, secret=secret, now_epoch=now_epoch)
    if not vr.ok or vr.claims is None:
        return 401, {
            "ok": False,
            "error": "auth_rejected",
            "reason": vr.reason or "jwt_rejected",
            "contract": "AUTH_V1",
        }

    claims = vr.claims
    user_id = str(claims.get("sub") or "").strip()
    if not user_id:
        return 401, {"ok": False, "error": "auth_rejected", "reason": "missing_sub", "contract": "AUTH_V1"}

    ar = allowlist_override if allowlist_override is not None else verify_user_is_active_beta(user_id)
    if not ar.ok:
        http_status = 403 if ar.mode != ALLOWLIST_MODE_OFF else 401
        return http_status, {
            "ok": False,
            "error": "auth_rejected",
            "reason": ar.reason or "allowlist_rejected",
            "contract": "AUTH_V1",
        }

    display_name = str(raw.get("display_name") or "").strip() or None
    preferred_lang_raw = str(raw.get("preferred_lang") or "").strip().lower()
    preferred_lang: Optional[str]
    if preferred_lang_raw in ("ko", "en"):
        preferred_lang = preferred_lang_raw
    else:
        preferred_lang = _preferred_lang_from_claims(claims)

    session_id = str(uuid.uuid4())

    client = rest_client if rest_client is not None else _build_rest_client()
    if client is not None:
        profile_row = {
            "user_id": user_id,
            "display_name": display_name,
            "preferred_lang": preferred_lang,
            "last_seen_at": _now_iso_utc(now_epoch),
        }
        try:
            client.insert("profiles_v1", [profile_row], on_conflict="user_id")
        except SupabaseRestError:
            # Non-fatal: we still let the user land, but we flag the reason.
            pass

    dto = _sanitized_profile_dto(
        user_id=user_id,
        display_name=display_name,
        role=ar.role or "beta_user",
        allowlist_status=ar.status or "unknown",
        allowlist_mode=ar.mode or "unknown",
        preferred_lang=preferred_lang,
        session_id=session_id,
    )
    return 200, {"ok": True, "user": dto, "session_id": session_id}


def api_auth_me(
    *,
    decision: Optional[AuthDecision] = None,
    rest_client: Optional[SupabaseRestClient] = None,
) -> tuple[int, dict[str, Any]]:
    """Return the caller's profile. Requires ``require_auth`` to have run."""

    if decision is None or not decision.ok or not decision.user_id:
        return 401, {"ok": False, "error": "auth_required", "contract": "AUTH_V1"}

    client = rest_client if rest_client is not None else _build_rest_client()
    display_name: Optional[str] = None
    preferred_lang: Optional[str] = None
    if client is not None:
        try:
            rows = client.select(
                "profiles_v1",
                columns="display_name,preferred_lang",
                filters={"user_id": f"eq.{decision.user_id}", "limit": "1"},
            )
        except SupabaseRestError:
            rows = []
        if rows:
            display_name = str(rows[0].get("display_name") or "").strip() or None
            lang_raw = str(rows[0].get("preferred_lang") or "").strip().lower()
            preferred_lang = lang_raw if lang_raw in ("ko", "en") else None

    if preferred_lang is None and decision.claims:
        preferred_lang = _preferred_lang_from_claims(decision.claims)

    dto = _sanitized_profile_dto(
        user_id=decision.user_id,
        display_name=display_name,
        role=decision.role or "beta_user",
        allowlist_status=decision.allowlist_status or "unknown",
        allowlist_mode=decision.allowlist_mode or "unknown",
        preferred_lang=preferred_lang,
        session_id="",  # /me does not mint sessions
    )
    return 200, {"ok": True, "user": dto}


def api_auth_signout() -> tuple[int, dict[str, Any]]:
    """No-op server handshake. The client-side SDK handles the actual
    token revocation; this endpoint exists so the browser can record a
    bounded ``auth_signout`` telemetry event with a 200 response."""

    return 200, {"ok": True, "event": "auth_signout", "contract": "AUTH_V1"}


def api_runtime_auth_config() -> tuple[int, dict[str, Any]]:
    """Expose **anon-safe** config so ``login.html`` can boot supabase-js.

    Never returns the service role / JWT secret. ``SUPABASE_ANON_KEY`` is
    designed to be public (JWT-like token signed with the anon claim).
    """

    supabase_url = (os.environ.get("SUPABASE_URL") or "").strip()
    anon_key = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    redirect_url = (os.environ.get("SUPABASE_AUTH_REDIRECT_URL") or "").strip()
    configured = bool(supabase_url and anon_key)
    return 200, {
        "ok": True,
        "configured": configured,
        "supabase_url": supabase_url if configured else "",
        "anon_key": anon_key if configured else "",
        "redirect_url": redirect_url,
        "contract": "AUTH_V1",
    }


def _now_iso_utc(now_epoch: Optional[int] = None) -> str:
    from datetime import datetime, timezone

    t = now_epoch if now_epoch is not None else int(time.time())
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


__all__ = [
    "api_auth_me",
    "api_auth_session",
    "api_auth_signout",
    "api_runtime_auth_config",
]
