"""Patch 12.1 — fallback access-token verification via Supabase ``/auth/v1/user``.

Context
-------
Patch 12 shipped a stdlib-only HS256 verifier (see
``jwt_verifier.verify_supabase_jwt``). New Supabase projects created in 2025
now default to **asymmetric signing keys** (``ES256`` / ``RS256``) — the HS256
legacy secret is still available but no longer the default for freshly
provisioned projects. Rather than pull in a third-party crypto library (which
would break the ``stdlib-only`` guarantee from the Patch 12 plan), we verify
those tokens by asking Supabase itself:

    GET {SUPABASE_URL}/auth/v1/user
    Authorization: Bearer <access_token>
    apikey: <SUPABASE_ANON_KEY>

Supabase performs the full signature + expiry + session-revocation check on
its end and returns the canonical user row on success. This costs one HTTPS
round-trip per login (and per non-``/api/auth/session`` call until the 30s
beta-allowlist cache warms up), which is acceptable for private-beta traffic.

The module is intentionally kept narrow:

* No state, no cache here — callers stack this after the local HS256 verifier
  and can layer caching on top if they need to.
* Never raises on network / HTTP errors — returns a reason so the guard can
  map it to a 401.
* Never leaks the raw token, email, or user id into logs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional


_DEFAULT_TIMEOUT_S: float = 5.0
_SAFE_REASONS: frozenset[str] = frozenset(
    {
        "supabase_not_configured",
        "missing_token",
        "network_error",
        "invalid_response",
        "missing_sub",
        "http_401",
        "http_403",
        "http_500",
        "http_502",
        "http_503",
        "http_504",
        "http_other",
    }
)


@dataclass(frozen=True)
class SupabaseUserVerifyResult:
    ok: bool
    claims: Optional[dict[str, Any]]
    reason: Optional[str]


def _http_reason(status_code: int) -> str:
    mapped = f"http_{status_code}"
    return mapped if mapped in _SAFE_REASONS else "http_other"


def verify_via_supabase_user_endpoint(
    token: str,
    *,
    supabase_url: Optional[str] = None,
    anon_key: Optional[str] = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    http_opener: Optional[Callable[[urllib.request.Request, float], Any]] = None,
) -> SupabaseUserVerifyResult:
    """Validate ``token`` by round-tripping ``GET /auth/v1/user``.

    Parameters
    ----------
    token:
        The Supabase access token (``eyJ...`` JWT).
    supabase_url, anon_key:
        Optional overrides. Defaults to ``SUPABASE_URL`` /
        ``SUPABASE_ANON_KEY`` env vars.
    timeout_s:
        Network timeout in seconds (default 5s). The guard path is
        synchronous so we intentionally stay conservative.
    http_opener:
        Test hook — a callable ``(request, timeout) -> response``.
        Defaults to ``urllib.request.urlopen``.
    """

    url = (supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (anon_key if anon_key is not None else os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not url or not key:
        return SupabaseUserVerifyResult(False, None, "supabase_not_configured")

    tok = (token or "").strip()
    if not tok:
        return SupabaseUserVerifyResult(False, None, "missing_token")

    req = urllib.request.Request(
        f"{url}/auth/v1/user",
        method="GET",
        headers={
            "Authorization": f"Bearer {tok}",
            "apikey": key,
            "Accept": "application/json",
        },
    )
    # Patch 12.2 — ``urllib.request.urlopen`` takes ``data`` as the second
    # positional argument (``urlopen(url, data=None, timeout=...)``), so the
    # original ``opener(req, timeout_s)`` call smuggled ``5.0`` into ``data``.
    # That flipped the GET to a POST with a float body, which blew up before
    # our except clauses could even catch ``URLError`` and surfaced as
    # Railway ``502 Application failed to respond``. Wrap the default so both
    # the real ``urlopen`` and the test opener share the positional
    # ``(request, timeout)`` convention.
    def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
        return urllib.request.urlopen(request, timeout=timeout)

    opener = http_opener if http_opener is not None else _default_opener
    try:
        resp = opener(req, timeout_s)
    except urllib.error.HTTPError as e:
        return SupabaseUserVerifyResult(False, None, _http_reason(int(getattr(e, "code", 0) or 0)))
    except (urllib.error.URLError, TimeoutError, OSError):
        return SupabaseUserVerifyResult(False, None, "network_error")
    except Exception:
        # Defense-in-depth: any other unexpected error (e.g. TypeError from a
        # pathological opener, SSL oddities) must *not* escape the guard and
        # turn into a 502. Surface it as a generic network_error.
        return SupabaseUserVerifyResult(False, None, "network_error")

    try:
        status = int(getattr(resp, "status", None) or getattr(resp, "code", None) or 0)
        body_bytes = resp.read()
    except Exception:  # pragma: no cover - defensive
        return SupabaseUserVerifyResult(False, None, "invalid_response")
    finally:
        try:
            resp.close()
        except Exception:
            pass

    if status != 200:
        return SupabaseUserVerifyResult(False, None, _http_reason(status))

    try:
        user = json.loads(body_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return SupabaseUserVerifyResult(False, None, "invalid_response")
    if not isinstance(user, dict):
        return SupabaseUserVerifyResult(False, None, "invalid_response")

    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return SupabaseUserVerifyResult(False, None, "missing_sub")

    claims: dict[str, Any] = {
        "sub": user_id,
        "email": str(user.get("email") or "") or "",
        "role": str(user.get("role") or "authenticated") or "authenticated",
        "aud": str(user.get("aud") or "authenticated") or "authenticated",
        "app_metadata": user.get("app_metadata") or {},
        "user_metadata": user.get("user_metadata") or {},
        "_verified_via": "supabase_user_endpoint",
    }
    return SupabaseUserVerifyResult(True, claims, None)


__all__ = [
    "SupabaseUserVerifyResult",
    "verify_via_supabase_user_endpoint",
]
