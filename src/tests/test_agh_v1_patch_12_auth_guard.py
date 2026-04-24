"""Patch 12 — ``/api/*`` auth guard (public allowlist + Bearer + graceful downgrade)."""

from __future__ import annotations

import time

from phase47_runtime.auth.beta_allowlist import BetaAllowlistResult, ALLOWLIST_MODE_ENFORCE, ALLOWLIST_MODE_OFF
from phase47_runtime.auth.guard import PUBLIC_API_PATHS, require_auth, user_id_alias
from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests


_SECRET = "jwt-secret-x"


def _valid_token(sub: str = "user-A"):
    now = int(time.time())
    return sign_hs256_for_tests(
        {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now - 5, "exp": now + 3600},
        secret=_SECRET,
    )


def _pass_allowlist(_user_id=None, **_kw):
    return BetaAllowlistResult(ok=True, user_id=_user_id or "user-A", status="active", role="beta_user", mode=ALLOWLIST_MODE_ENFORCE)


def test_public_paths_bypass_guard():
    for p in PUBLIC_API_PATHS:
        d = require_auth(method="GET", path=p, headers={}, jwt_secret=_SECRET)
        assert d.ok, (p, d.reason)


def test_missing_bearer_on_protected_path_returns_401():
    d = require_auth(method="GET", path="/api/product/today", headers={}, jwt_secret=_SECRET, allowlist=_pass_allowlist)
    assert not d.ok and d.http_status == 401 and d.reason == "missing_bearer_token"


def test_valid_bearer_passes_guard():
    tok = _valid_token()
    d = require_auth(
        method="GET",
        path="/api/product/today",
        headers={"Authorization": f"Bearer {tok}"},
        jwt_secret=_SECRET,
        allowlist=_pass_allowlist,
    )
    assert d.ok, d.reason
    assert d.user_id == "user-A"
    assert d.user_id_alias and d.user_id_alias.startswith("bu_")


def test_graceful_downgrade_when_no_jwt_secret():
    # Even on a protected path, if SUPABASE_JWT_SECRET is missing the guard
    # no-ops so local dev + CI keep working.
    d = require_auth(method="GET", path="/api/product/today", headers={}, jwt_secret="")
    assert d.ok and d.reason == "auth_not_configured"


def test_revoked_user_gets_403():
    def revoked(_uid=None, **_kw):
        return BetaAllowlistResult(ok=False, user_id=_uid or "u", status="revoked", role="beta_user",
                                   mode=ALLOWLIST_MODE_ENFORCE, reason="allowlist_revoked")
    tok = _valid_token()
    d = require_auth(
        method="GET",
        path="/api/product/today",
        headers={"Authorization": f"Bearer {tok}"},
        jwt_secret=_SECRET,
        allowlist=revoked,
    )
    assert not d.ok and d.http_status == 403 and d.reason == "allowlist_revoked"


def test_bad_signature_rejected():
    tok = _valid_token()
    d = require_auth(
        method="GET",
        path="/api/product/today",
        headers={"Authorization": f"Bearer {tok}"},
        jwt_secret="different-secret",
        allowlist=_pass_allowlist,
    )
    assert not d.ok and d.http_status == 401 and d.reason == "bad_signature"


def test_options_preflight_bypasses_guard():
    d = require_auth(method="OPTIONS", path="/api/product/today", headers={}, jwt_secret=_SECRET)
    assert d.ok


def test_user_id_alias_stable():
    a = user_id_alias("user-A")
    b = user_id_alias("user-A")
    c = user_id_alias("user-B")
    assert a == b
    assert a != c
    assert a.startswith("bu_") and len(a) == 15
