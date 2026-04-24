"""Patch 12 — HS256 JWT verifier (stdlib only)."""

from __future__ import annotations

import time

import pytest

from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests, verify_supabase_jwt


_SECRET = "test-secret-x"


def _payload(**over):
    base = {"sub": "user-1", "aud": "authenticated", "role": "authenticated",
            "iat": int(time.time()) - 10, "exp": int(time.time()) + 3600}
    base.update(over)
    return base


def test_roundtrip_valid_token_verifies():
    tok = sign_hs256_for_tests(_payload(), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert res.ok, res.reason
    assert res.claims and res.claims["sub"] == "user-1"


def test_wrong_secret_rejected():
    tok = sign_hs256_for_tests(_payload(), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret="other-secret")
    assert not res.ok
    assert res.reason == "bad_signature"


def test_expired_rejected():
    past = int(time.time()) - 3600
    tok = sign_hs256_for_tests(_payload(iat=past - 10, exp=past), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert not res.ok and res.reason == "expired"


def test_malformed_rejected():
    res = verify_supabase_jwt("not.a.jwt.too.many", secret=_SECRET)
    assert not res.ok and res.reason == "malformed"
    res2 = verify_supabase_jwt("", secret=_SECRET)
    assert not res2.ok and res2.reason == "malformed"


def test_wrong_audience_rejected():
    tok = sign_hs256_for_tests(_payload(aud="anon"), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert not res.ok and res.reason == "wrong_audience"


def test_missing_sub_rejected():
    p = _payload()
    p.pop("sub")
    tok = sign_hs256_for_tests(p, secret=_SECRET)
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert not res.ok and res.reason == "missing_sub"


def test_wrong_role_rejected():
    tok = sign_hs256_for_tests(_payload(role="service_role"), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert not res.ok and res.reason == "missing_role"


def test_forged_header_rejected():
    tok = sign_hs256_for_tests(_payload(), secret=_SECRET)
    h, p, s = tok.split(".")
    # swap header to RS256 — signature won't re-match
    forged = "eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9" + "." + p + "." + s
    res = verify_supabase_jwt(forged, secret=_SECRET)
    assert not res.ok
    assert res.reason in ("unsupported_alg", "bad_signature")


def test_empty_secret_rejected():
    tok = sign_hs256_for_tests(_payload(), secret=_SECRET)
    res = verify_supabase_jwt(tok, secret="")
    assert not res.ok and res.reason == "empty_secret"


def test_unknown_alg_rejected():
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(_payload()).encode()).rstrip(b"=").decode()
    tok = f"{header}.{payload}."
    res = verify_supabase_jwt(tok, secret=_SECRET)
    assert not res.ok
    assert res.reason in ("unsupported_alg", "malformed", "bad_signature")
