"""Patch 12 — stdlib-only HS256 JWT verifier for Supabase access tokens.

Supabase's default access token is a signed JWT using the project's
``JWT_SECRET``. We verify it locally so every ``/api/*`` request can attach
``user_id``/``email`` claims without round-tripping to Supabase Auth.

Design notes:

* No third-party dependency — uses ``hmac``, ``hashlib``, ``base64``, ``json``
  only, per Patch 12 plan §M1 (stdlib JWT verify).
* HS256 only. If Supabase ever migrates to RS256 we will swap this module.
* Constant-time signature comparison via ``hmac.compare_digest``.
* The return contract is ``JwtVerifyResult`` — never raise on bad tokens;
  the guard turns a negative result into a ``401``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any


_ALLOWED_ALG = "HS256"
_ALLOWED_REASONS = frozenset(
    {
        "malformed",
        "unsupported_alg",
        "bad_signature",
        "expired",
        "not_yet_valid",
        "wrong_audience",
        "missing_sub",
        "missing_role",
        "empty_secret",
    }
)


@dataclass(frozen=True)
class JwtVerifyResult:
    ok: bool
    claims: dict[str, Any] | None
    reason: str | None

    def to_safe_error(self) -> dict[str, Any]:
        """Produce a safe error payload (never leaks the raw JWT)."""

        return {
            "ok": False,
            "error": "auth_rejected",
            "reason": self.reason or "unknown",
            "contract": "AUTH_V1",
        }


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def verify_supabase_jwt(
    token: str,
    *,
    secret: str,
    expected_audience: str = "authenticated",
    leeway_seconds: int = 5,
    now_epoch: int | None = None,
) -> JwtVerifyResult:
    """Verify a Supabase HS256 JWT. Returns (ok, claims, reason)."""

    if not secret or not str(secret).strip():
        return JwtVerifyResult(False, None, "empty_secret")
    if not token or not isinstance(token, str):
        return JwtVerifyResult(False, None, "malformed")

    parts = token.split(".")
    if len(parts) != 3:
        return JwtVerifyResult(False, None, "malformed")
    header_b64, payload_b64, sig_b64 = parts

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        sig = _b64url_decode(sig_b64)
    except (ValueError, UnicodeDecodeError):
        return JwtVerifyResult(False, None, "malformed")

    if not isinstance(header, dict) or not isinstance(payload, dict):
        return JwtVerifyResult(False, None, "malformed")

    alg = str(header.get("alg") or "").upper()
    if alg != _ALLOWED_ALG:
        return JwtVerifyResult(False, None, "unsupported_alg")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        return JwtVerifyResult(False, None, "bad_signature")

    now = int(now_epoch if now_epoch is not None else time.time())
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and int(exp) + leeway_seconds < now:
        return JwtVerifyResult(False, None, "expired")
    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and int(nbf) > now + leeway_seconds:
        return JwtVerifyResult(False, None, "not_yet_valid")
    iat = payload.get("iat")
    if isinstance(iat, (int, float)) and int(iat) > now + leeway_seconds * 12:
        # guard against grossly future-dated tokens
        return JwtVerifyResult(False, None, "not_yet_valid")

    aud = payload.get("aud")
    if expected_audience:
        if isinstance(aud, str):
            if aud != expected_audience:
                return JwtVerifyResult(False, None, "wrong_audience")
        elif isinstance(aud, list):
            if expected_audience not in aud:
                return JwtVerifyResult(False, None, "wrong_audience")
        else:
            return JwtVerifyResult(False, None, "wrong_audience")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return JwtVerifyResult(False, None, "missing_sub")

    role = str(payload.get("role") or "")
    if role and role != "authenticated":
        # Supabase service/anon tokens should never hit the auth guard;
        # beta users always have ``role=authenticated``.
        return JwtVerifyResult(False, None, "missing_role")

    return JwtVerifyResult(True, dict(payload), None)


def sign_hs256_for_tests(
    payload: dict[str, Any], *, secret: str, kid: str | None = None
) -> str:
    """Produce an HS256 token — used exclusively by the Patch 12 tests.

    Kept in production code (rather than a test helper) so the freeze
    scripts can round-trip without pulling a third-party JWT library.
    """

    header: dict[str, Any] = {"alg": _ALLOWED_ALG, "typ": "JWT"}
    if kid:
        header["kid"] = kid
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


__all__ = [
    "JwtVerifyResult",
    "verify_supabase_jwt",
    "sign_hs256_for_tests",
]
