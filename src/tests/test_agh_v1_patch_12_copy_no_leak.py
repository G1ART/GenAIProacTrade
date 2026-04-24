"""Patch 12 — no-leak assertions for /login.html + auth/admin DTOs."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from phase47_runtime.auth.guard import AuthDecision
from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests
from phase47_runtime.routes_admin import api_admin_beta_users
from phase47_runtime.routes_auth import (
    api_auth_me,
    api_auth_session,
    api_runtime_auth_config,
)


_STATIC = Path(__file__).resolve().parents[1] / "phase47_runtime" / "static"


# ---------------------------------------------------------------------
# 1. /login.html static assets
# ---------------------------------------------------------------------

def test_login_html_has_no_secret_substring():
    html = (_STATIC / "login.html").read_text(encoding="utf-8")
    # Never embed any secret-ish string directly into a shipped HTML.
    for banned in ("SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY", "service_role"):
        assert banned not in html, banned


def test_login_js_has_no_secret_substring():
    js = (_STATIC / "login.js").read_text(encoding="utf-8")
    for banned in ("SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY", "service_role"):
        assert banned not in js, banned


def test_login_page_uses_anon_config_endpoint():
    js = (_STATIC / "login.js").read_text(encoding="utf-8")
    assert "/api/runtime/auth-config" in js


# ---------------------------------------------------------------------
# 2. Auth runtime DTOs — never leak raw user_id / email / JWT
# ---------------------------------------------------------------------

def test_auth_config_never_includes_service_role_or_jwt_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "public-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "DO_NOT_LEAK_service_role_secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "DO_NOT_LEAK_jwt_secret")
    code, body = api_runtime_auth_config()
    assert code == 200
    raw = json.dumps(body)
    assert "DO_NOT_LEAK_service_role_secret" not in raw
    assert "DO_NOT_LEAK_jwt_secret" not in raw
    # but anon_key is allowed (supabase-js needs it)
    assert body["anon_key"] == "public-anon-key"


def test_auth_session_dto_hides_raw_user_id_and_email(monkeypatch):
    secret = "jwt-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    now = int(time.time())
    payload = {"sub": "11111111-2222-3333-4444-555555555555",
               "email": "alice@example.com",
               "aud": "authenticated", "role": "authenticated",
               "iat": now - 10, "exp": now + 3600}
    tok = sign_hs256_for_tests(payload, secret=secret)
    from phase47_runtime.auth.beta_allowlist import BetaAllowlistResult, ALLOWLIST_MODE_ENFORCE
    override = BetaAllowlistResult(ok=True, user_id=payload["sub"], status="active",
                                   role="beta_user", mode=ALLOWLIST_MODE_ENFORCE)
    code, body = api_auth_session(
        {"access_token": tok, "preferred_lang": "ko"},
        rest_client=None,
        allowlist_override=override,
    )
    assert code == 200 and body["ok"]
    dto = json.dumps(body)
    assert payload["sub"] not in dto
    assert "alice@example.com" not in dto
    assert body["user"]["user_id_alias"].startswith("bu_")


def test_auth_me_dto_hides_raw_user_id(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    decision = AuthDecision(
        ok=True, http_status=200,
        user_id="99999999-0000-0000-0000-000000000000",
        user_id_alias="bu_abcdef123456",
        role="beta_user", allowlist_status="active", allowlist_mode="enforce",
        reason=None, claims={"sub": "99999999-0000-0000-0000-000000000000"},
    )
    code, body = api_auth_me(decision=decision, rest_client=None)
    assert code == 200
    raw = json.dumps(body)
    assert "99999999-0000-0000-0000-000000000000" not in raw


def test_admin_users_dto_hides_raw_user_id_and_email():
    @dataclass
    class Fake:
        rows: list[dict[str, Any]]
        def select(self, table, *, columns, filters=None, limit=None, order=None):
            return self.rows

    client = Fake(rows=[
        {"user_id": "abcd1234-0000-0000-0000-000000000000",
         "email": "jane.doe@secret-company.com",
         "status": "active", "role": "beta_user",
         "invited_at": "2026-04-20T00:00:00Z", "activated_at": None},
    ])
    decision = AuthDecision(ok=True, http_status=200, user_id="admin1",
                            user_id_alias="bu_deadbeef1234", role="admin",
                            allowlist_status="active", allowlist_mode="enforce",
                            reason=None, claims=None)
    code, body = api_admin_beta_users(decision=decision, client=client)
    assert code == 200
    raw = json.dumps(body)
    assert "abcd1234-0000-0000-0000-000000000000" not in raw
    assert "jane.doe@secret-company.com" not in raw
    # domain may remain in masked email — that's OK (audit + invite validation)
    # but the local-part must be obscured
    assert body["items"][0]["email_masked"].startswith("j•")


# ---------------------------------------------------------------------
# 3. error paths must not echo raw email / token
# ---------------------------------------------------------------------

def test_auth_session_error_never_echoes_access_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "real-secret")
    bogus = "tampered.jwt.value-NEVER-ECHO"
    code, body = api_auth_session({"access_token": bogus}, rest_client=None)
    assert code in (400, 401)
    assert bogus not in json.dumps(body)
