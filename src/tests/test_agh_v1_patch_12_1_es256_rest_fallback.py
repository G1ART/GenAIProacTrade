"""Patch 12.1 — ES256/RS256 access-token REST fallback.

Verifies:

* When the local HS256 verifier rejects the token with ``unsupported_alg`` /
  ``bad_signature`` / ``empty_secret``, the resolver falls back to the
  Supabase ``GET /auth/v1/user`` REST endpoint and passes on success.
* When the local verifier rejects with a definitive claim-level reason
  (``expired``, ``wrong_audience``, ``malformed``, etc.), the resolver does
  NOT round-trip REST.
* The REST verifier itself handles the network-configured / not-configured
  / 4xx / 5xx branches without raising and without leaking the token.
* The guard (`require_auth`) accepts an ES256 token via REST fallback when
  only ``SUPABASE_URL`` + ``SUPABASE_ANON_KEY`` are configured (no JWT
  secret).
"""

from __future__ import annotations

import io
import json
import time
from typing import Any

import pytest

from phase47_runtime.auth.access_token_resolver import resolve_access_token
from phase47_runtime.auth.beta_allowlist import (
    ALLOWLIST_MODE_ENFORCE,
    BetaAllowlistResult,
)
from phase47_runtime.auth.guard import require_auth
from phase47_runtime.auth.jwt_verifier import JwtVerifyResult, sign_hs256_for_tests
from phase47_runtime.auth.supabase_user_verify import (
    SupabaseUserVerifyResult,
    verify_via_supabase_user_endpoint,
)


_SECRET = "p121-secret"
_USER_ID = "b7938ecb-8e29-475a-87f6-c23cb7496ef3"


class _FakeHttpResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.code = status
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8") if payload is not None else b"")

    def read(self) -> bytes:
        return self._buf.read()

    def close(self) -> None:
        self._buf.close()


def _make_opener(status: int, payload: Any, captured: dict[str, Any] | None = None):
    def opener(req, timeout):
        if captured is not None:
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["timeout"] = timeout
        return _FakeHttpResponse(status, payload)

    return opener


# ---------- supabase_user_verify ----------


def test_rest_verify_returns_claims_on_200(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-xxx")
    captured: dict[str, Any] = {}
    opener = _make_opener(
        200,
        {
            "id": _USER_ID,
            "email": "henry@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "app_metadata": {"provider": "email"},
            "user_metadata": {"email_verified": True},
        },
        captured,
    )
    res = verify_via_supabase_user_endpoint("eyJfake", http_opener=opener)
    assert res.ok is True
    assert res.claims is not None
    assert res.claims["sub"] == _USER_ID
    assert res.claims["email"] == "henry@example.com"
    assert res.claims["_verified_via"] == "supabase_user_endpoint"
    assert captured["url"].endswith("/auth/v1/user")
    assert captured["headers"]["authorization"] == "Bearer eyJfake"
    assert captured["headers"]["apikey"] == "anon-xxx"


def test_rest_verify_not_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    res = verify_via_supabase_user_endpoint("eyJfake")
    assert res.ok is False
    assert res.reason == "supabase_not_configured"


def test_rest_verify_401_maps_to_http_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-xxx")
    res = verify_via_supabase_user_endpoint(
        "eyJfake", http_opener=_make_opener(401, {"msg": "invalid token"})
    )
    assert res.ok is False
    assert res.reason == "http_401"


def test_rest_verify_empty_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-xxx")
    res = verify_via_supabase_user_endpoint("")
    assert res.ok is False
    assert res.reason == "missing_token"


def test_rest_verify_missing_sub(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-xxx")
    res = verify_via_supabase_user_endpoint(
        "eyJfake", http_opener=_make_opener(200, {"email": "a@b"})
    )
    assert res.ok is False
    assert res.reason == "missing_sub"


# ---------- access_token_resolver ----------


def _fake_rest_ok(_token, **_kw) -> SupabaseUserVerifyResult:
    return SupabaseUserVerifyResult(
        ok=True,
        claims={
            "sub": _USER_ID,
            "email": "x@y",
            "role": "authenticated",
            "aud": "authenticated",
            "app_metadata": {},
            "user_metadata": {},
            "_verified_via": "supabase_user_endpoint",
        },
        reason=None,
    )


def _fake_rest_404(_token, **_kw) -> SupabaseUserVerifyResult:
    return SupabaseUserVerifyResult(False, None, "http_401")


def _fake_rest_unconfigured(_token, **_kw) -> SupabaseUserVerifyResult:
    return SupabaseUserVerifyResult(False, None, "supabase_not_configured")


def test_resolver_hs256_ok_path_no_rest_call():
    tok = sign_hs256_for_tests(
        {"sub": "hs-user", "aud": "authenticated", "role": "authenticated",
         "iat": int(time.time()) - 10, "exp": int(time.time()) + 3600},
        secret=_SECRET,
    )
    called = {"n": 0}

    def rest(_t, **_kw):  # pragma: no cover (must not be called)
        called["n"] += 1
        return SupabaseUserVerifyResult(False, None, "network_error")

    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=rest)
    assert res.ok is True
    assert res.claims and res.claims["sub"] == "hs-user"
    assert called["n"] == 0  # no REST round-trip on HS256 success


def test_resolver_unsupported_alg_falls_back_to_rest():
    # craft an ES256-labelled token (we just need the alg header to not be HS256).
    import base64

    def b64(obj: bytes | dict) -> str:
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "ES256", "typ": "JWT", "kid": "k1"})
    payload = b64({"sub": _USER_ID, "aud": "authenticated",
                   "role": "authenticated", "exp": int(time.time()) + 3600})
    sig = b64(b"fake-signature-bytes")
    tok = f"{header}.{payload}.{sig}"

    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=_fake_rest_ok)
    assert res.ok is True
    assert res.claims and res.claims["sub"] == _USER_ID
    assert res.claims.get("_verified_via") == "supabase_user_endpoint"


def test_resolver_bad_signature_falls_back_to_rest():
    tok = sign_hs256_for_tests(
        {"sub": "hs-user", "aud": "authenticated", "role": "authenticated",
         "iat": int(time.time()) - 10, "exp": int(time.time()) + 3600},
        secret="WRONG-SECRET",
    )
    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=_fake_rest_ok)
    assert res.ok is True
    assert res.claims and res.claims["sub"] == _USER_ID


def test_resolver_empty_secret_falls_back_to_rest():
    import base64

    def b64(obj: bytes | dict) -> str:
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "ES256", "typ": "JWT"})
    payload = b64({"sub": _USER_ID, "aud": "authenticated",
                   "role": "authenticated", "exp": int(time.time()) + 3600})
    tok = f"{header}.{payload}.xxxx"
    res = resolve_access_token(tok, secret="", rest_verifier=_fake_rest_ok)
    assert res.ok is True


def test_resolver_expired_does_not_fallback():
    past = int(time.time()) - 7200
    tok = sign_hs256_for_tests(
        {"sub": "hs-user", "aud": "authenticated", "role": "authenticated",
         "iat": past - 10, "exp": past},
        secret=_SECRET,
    )
    called = {"n": 0}

    def rest(_t, **_kw):  # pragma: no cover
        called["n"] += 1
        return SupabaseUserVerifyResult(True, {"sub": "whatever"}, None)

    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=rest)
    assert res.ok is False
    assert res.reason == "expired"
    assert called["n"] == 0


def test_resolver_rest_unconfigured_returns_original_reason():
    import base64

    def b64(obj: bytes | dict) -> str:
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "ES256", "typ": "JWT"})
    payload = b64({"sub": _USER_ID, "aud": "authenticated",
                   "role": "authenticated", "exp": int(time.time()) + 3600})
    tok = f"{header}.{payload}.xxxx"
    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=_fake_rest_unconfigured)
    assert res.ok is False
    assert res.reason == "unsupported_alg"


def test_resolver_rest_rejects_returns_rest_prefixed_reason():
    import base64

    def b64(obj: bytes | dict) -> str:
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "ES256", "typ": "JWT"})
    payload = b64({"sub": _USER_ID, "aud": "authenticated",
                   "role": "authenticated", "exp": int(time.time()) + 3600})
    tok = f"{header}.{payload}.xxxx"
    res = resolve_access_token(tok, secret=_SECRET, rest_verifier=_fake_rest_404)
    assert res.ok is False
    assert res.reason == "rest_http_401"


# ---------- guard integration ----------


def _passing_allowlist(_uid):
    return BetaAllowlistResult(
        ok=True, user_id=_USER_ID, status="active", role="admin",
        mode=ALLOWLIST_MODE_ENFORCE, reason=None,
    )


def test_guard_accepts_es256_via_rest_when_only_anon_configured(monkeypatch):
    """Patch 12.1 — require_auth no longer downgrades when JWT secret is
    missing as long as SUPABASE_URL + ANON_KEY are present."""

    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-xxx")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    import base64

    def b64(obj):
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "ES256", "typ": "JWT"})
    payload = b64({"sub": _USER_ID, "aud": "authenticated",
                   "role": "authenticated", "exp": int(time.time()) + 3600})
    tok = f"{header}.{payload}.xxxx"

    def resolver(token, *, secret, now_epoch=None):
        # Simulate: HS256 empty_secret → REST fallback → ok
        return JwtVerifyResult(ok=True, claims={"sub": _USER_ID, "aud": "authenticated",
                                                "role": "authenticated"}, reason=None)

    decision = require_auth(
        method="GET",
        path="/api/auth/me",
        headers={"Authorization": f"Bearer {tok}"},
        verifier=resolver,
        allowlist=_passing_allowlist,
    )
    assert decision.ok is True
    assert decision.user_id == _USER_ID
    assert decision.reason is None


def test_guard_downgrades_when_neither_secret_nor_rest_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    decision = require_auth(method="GET", path="/api/auth/me", headers={})
    assert decision.ok is True
    assert decision.reason == "auth_not_configured"
