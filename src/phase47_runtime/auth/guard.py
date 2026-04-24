"""Patch 12 — ``/api/*`` auth guard used by ``dispatch_json``.

The guard is intentionally small: it parses the ``Authorization`` header,
verifies the Supabase JWT locally, checks the beta allowlist (unless the
operator has set ``METIS_BETA_ALLOWLIST_MODE=off`` — e.g. local dev), and
returns an ``AuthDecision``.

Routes that must stay publicly reachable (health-check, auth callbacks,
the Product Shell bootstrap probe) are listed in ``PUBLIC_API_PATHS``.
The remainder of the API requires a valid bearer token plus an invited /
active beta allowlist row.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from phase47_runtime.auth.access_token_resolver import resolve_access_token
from phase47_runtime.auth.beta_allowlist import (
    ALLOWLIST_MODE_OFF,
    BetaAllowlistResult,
    verify_user_is_active_beta,
)
from phase47_runtime.auth.jwt_verifier import JwtVerifyResult, verify_supabase_jwt  # noqa: F401  (re-exported for tests)


PUBLIC_API_PATHS: frozenset[str] = frozenset(
    {
        "/api/runtime/health",
        "/api/runtime/auth-config",
        "/api/auth/session",
        "/api/auth/signout",
    }
)


@dataclass(frozen=True)
class AuthDecision:
    ok: bool
    http_status: int
    user_id: Optional[str]
    user_id_alias: Optional[str]
    role: Optional[str]
    allowlist_status: Optional[str]
    allowlist_mode: Optional[str]
    reason: Optional[str]
    claims: Optional[dict[str, Any]]

    def to_error_payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "auth_rejected",
            "reason": self.reason or "unknown",
            "contract": "AUTH_V1",
        }


def user_id_alias(user_id: str, *, prefix: str = "bu_") -> str:
    """Stable 12-char hash alias. Keeps raw UUIDs out of DTOs / logs.

    Uses SHA-256 (matches the engineering-id guard style used elsewhere
    in the codebase for hashing persona/overlay IDs).
    """

    if not user_id:
        return ""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:12]}"


def _extract_bearer(headers: Optional[dict[str, str]]) -> Optional[str]:
    if not headers:
        return None
    for key in ("Authorization", "authorization", "X-Authorization"):
        raw = headers.get(key)
        if not raw:
            continue
        raw = str(raw).strip()
        if raw.lower().startswith("bearer "):
            token = raw.split(" ", 1)[1].strip()
            if token:
                return token
    return None


def _jwt_secret() -> str:
    return (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()


def _rest_fallback_configured() -> bool:
    """Patch 12.1 — true when SUPABASE_URL + ANON_KEY are set.

    Required because new Supabase projects (2025+) ship ES256 JWTs that
    our stdlib HS256 verifier cannot check locally. With URL+anon key we
    can still verify by calling ``GET /auth/v1/user`` on Supabase itself.
    """

    url_ok = bool((os.environ.get("SUPABASE_URL") or "").strip())
    key_ok = bool((os.environ.get("SUPABASE_ANON_KEY") or "").strip())
    return url_ok and key_ok


def require_auth(
    *,
    method: str,
    path: str,
    headers: Optional[dict[str, str]] = None,
    public_paths: Iterable[str] = PUBLIC_API_PATHS,
    jwt_secret: Optional[str] = None,
    allowlist_result: Optional[BetaAllowlistResult] = None,
    now_epoch: Optional[int] = None,
    verifier=resolve_access_token,
    allowlist=verify_user_is_active_beta,
) -> AuthDecision:
    """Gate an API request. ``dispatch_json`` calls this first."""

    if (method or "").upper() == "OPTIONS":
        return AuthDecision(
            ok=True,
            http_status=200,
            user_id=None,
            user_id_alias=None,
            role=None,
            allowlist_status=None,
            allowlist_mode=None,
            reason=None,
            claims=None,
        )

    public_set = set(public_paths)
    if path in public_set:
        return AuthDecision(
            ok=True,
            http_status=200,
            user_id=None,
            user_id_alias=None,
            role=None,
            allowlist_status=None,
            allowlist_mode=None,
            reason=None,
            claims=None,
        )

    secret = jwt_secret if jwt_secret is not None else _jwt_secret()
    # Patch 12.1 — auth is considered "configured" if EITHER the HS256 secret
    # is set (legacy path) OR the REST fallback (SUPABASE_URL + ANON_KEY) is
    # available. Only when neither is present do we downgrade to no-op, which
    # keeps local dev + CI test suites working unchanged.
    rest_ok = _rest_fallback_configured()
    if not secret and not rest_ok:
        return AuthDecision(
            ok=True,
            http_status=200,
            user_id=None,
            user_id_alias=None,
            role=None,
            allowlist_status="unknown",
            allowlist_mode="off",
            reason="auth_not_configured",
            claims=None,
        )

    token = _extract_bearer(headers)
    if not token:
        return AuthDecision(
            ok=False,
            http_status=401,
            user_id=None,
            user_id_alias=None,
            role=None,
            allowlist_status=None,
            allowlist_mode=None,
            reason="missing_bearer_token",
            claims=None,
        )

    vr: JwtVerifyResult = verifier(token, secret=secret, now_epoch=now_epoch)
    if not vr.ok or vr.claims is None:
        return AuthDecision(
            ok=False,
            http_status=401,
            user_id=None,
            user_id_alias=None,
            role=None,
            allowlist_status=None,
            allowlist_mode=None,
            reason=vr.reason or "jwt_rejected",
            claims=None,
        )

    user_id = str(vr.claims.get("sub") or "").strip()
    alias = user_id_alias(user_id) if user_id else None

    ar = allowlist_result if allowlist_result is not None else allowlist(user_id)
    if not ar.ok:
        http_status = 403 if ar.mode != ALLOWLIST_MODE_OFF else 401
        return AuthDecision(
            ok=False,
            http_status=http_status,
            user_id=user_id,
            user_id_alias=alias,
            role=ar.role,
            allowlist_status=ar.status,
            allowlist_mode=ar.mode,
            reason=ar.reason or "allowlist_rejected",
            claims=vr.claims,
        )

    return AuthDecision(
        ok=True,
        http_status=200,
        user_id=user_id,
        user_id_alias=alias,
        role=ar.role,
        allowlist_status=ar.status,
        allowlist_mode=ar.mode,
        reason=None,
        claims=vr.claims,
    )


__all__ = [
    "AuthDecision",
    "PUBLIC_API_PATHS",
    "require_auth",
    "user_id_alias",
]
