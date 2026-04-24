"""Patch 12.1 — unified access-token claim resolver.

Supabase projects shipped in 2025 default to asymmetric signing keys
(ES256/RS256). Patch 12's stdlib-only HS256 verifier still handles the
legacy secret path, but for new projects the signatures are unverifiable
locally without adding a third-party crypto library.

Rather than split the call sites or add a crypto dependency, this
resolver layers:

1. **Local HS256 verify** (fast path — no network) via
   :func:`phase47_runtime.auth.jwt_verifier.verify_supabase_jwt`.
2. **Supabase ``GET /auth/v1/user`` REST fallback** via
   :func:`phase47_runtime.auth.supabase_user_verify.verify_via_supabase_user_endpoint`
   when the local verifier rejects the token *only* because the
   algorithm or signature couldn't be handled (``unsupported_alg``,
   ``bad_signature``, ``empty_secret``).

Definitive claim-level rejections (``expired``, ``not_yet_valid``,
``wrong_audience``, ``missing_sub``, ``missing_role``, ``malformed``)
short-circuit and never fall back — those are unambiguous protocol
violations and Supabase would reject them identically.

The output shape stays ``JwtVerifyResult`` so existing call sites
(``require_auth``, ``api_auth_session``) can keep their types.
"""

from __future__ import annotations

from typing import Optional

from phase47_runtime.auth.jwt_verifier import JwtVerifyResult, verify_supabase_jwt
from phase47_runtime.auth.supabase_user_verify import (
    SupabaseUserVerifyResult,
    verify_via_supabase_user_endpoint,
)


_FALLBACK_TRIGGERS: frozenset[str] = frozenset(
    {
        "unsupported_alg",
        "bad_signature",
        "empty_secret",
    }
)


def resolve_access_token(
    token: str,
    *,
    secret: str,
    now_epoch: Optional[int] = None,
    local_verifier=verify_supabase_jwt,
    rest_verifier=verify_via_supabase_user_endpoint,
) -> JwtVerifyResult:
    """Resolve ``token`` to a :class:`JwtVerifyResult` via HS256 → REST fallback."""

    vr = local_verifier(token, secret=secret, now_epoch=now_epoch)
    if vr.ok and vr.claims is not None:
        return vr

    if vr.reason not in _FALLBACK_TRIGGERS:
        return vr

    rr: SupabaseUserVerifyResult = rest_verifier(token)
    if rr.ok and rr.claims is not None:
        return JwtVerifyResult(ok=True, claims=dict(rr.claims), reason=None)

    if rr.reason == "supabase_not_configured":
        return vr

    suffix = rr.reason or "unknown"
    return JwtVerifyResult(ok=False, claims=None, reason=f"rest_{suffix}")


__all__ = ["resolve_access_token"]
