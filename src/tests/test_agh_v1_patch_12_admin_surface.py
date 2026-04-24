"""Patch 12 — /api/admin/beta/* RBAC + DTO shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from phase47_runtime.auth.guard import AuthDecision
from phase47_runtime.routes_admin import (
    api_admin_beta_events,
    api_admin_beta_sessions,
    api_admin_beta_trust,
    api_admin_beta_users,
)


@dataclass
class FakeRest:
    rows_by_table: dict[str, list[dict[str, Any]]]

    def select(self, table, *, columns, filters=None, limit=None, order=None):
        return self.rows_by_table.get(table, [])


def _decision(role: str, ok: bool = True, user_id: str = "u-admin") -> AuthDecision:
    return AuthDecision(
        ok=ok,
        http_status=200 if ok else 401,
        user_id=user_id if ok else None,
        user_id_alias="bu_deadbeef1234" if ok else None,
        role=role,
        allowlist_status="active",
        allowlist_mode="enforce",
        reason=None if ok else "x",
        claims=None,
    )


def test_no_auth_returns_401():
    code, body = api_admin_beta_users(decision=None)
    assert code == 401 and body["error"] == "auth_required"


def test_beta_user_role_gets_403():
    code, body = api_admin_beta_users(decision=_decision("beta_user"))
    assert code == 403 and body["error"] == "admin_required"


def test_admin_role_sees_users_with_aliases_no_raw_email():
    client = FakeRest(rows_by_table={
        "beta_users_v1": [
            {"user_id": "u1", "email": "jane@example.com", "status": "active", "role": "beta_user",
             "invited_at": "2026-04-20T00:00:00Z", "activated_at": "2026-04-21T00:00:00Z"},
            {"user_id": "u2", "email": "a@b.co", "status": "invited", "role": "admin",
             "invited_at": "2026-04-22T00:00:00Z", "activated_at": None},
        ],
    })
    code, body = api_admin_beta_users(decision=_decision("admin"), client=client)
    assert code == 200 and body["ok"]
    items = body["items"]
    assert len(items) == 2
    # no raw UUID
    for it in items:
        assert "user_id" not in it
        assert it["user_id_alias"].startswith("bu_")
        # no raw email
        assert "email" not in it
        assert "@" in it["email_masked"]
        assert "jane" not in it["email_masked"]


def test_internal_role_sees_sessions_with_aliases():
    client = FakeRest(rows_by_table={
        "v_beta_sessions_recent_v1": [
            {"user_id": "u1", "session_id": "s1", "event_count": 7,
             "session_started_at": "2026-04-23T00:00:00Z",
             "session_last_event_at": "2026-04-23T00:30:00Z",
             "surfaces_touched": ["today", "research"]},
        ],
    })
    code, body = api_admin_beta_sessions(decision=_decision("internal"), client=client)
    assert code == 200 and body["count"] == 1
    assert body["items"][0]["user_id_alias"].startswith("bu_")
    assert "user_id" not in body["items"][0]


def test_admin_events_and_trust_shape():
    client = FakeRest(rows_by_table={
        "v_beta_top_events_v1": [
            {"event_name": "page_view", "event_count": 12, "unique_users": 3, "unique_sessions": 5},
        ],
        "v_beta_trust_signals_v1": [
            {"total_ask_events": 10, "degraded_count": 2, "blocked_count": 0,
             "out_of_scope_count": 1, "ask_degraded_rate": 0.2, "out_of_scope_rate": 0.1},
        ],
    })
    c1, b1 = api_admin_beta_events(decision=_decision("admin"), client=client)
    assert c1 == 200 and b1["items"][0]["event_name"] == "page_view"

    c2, b2 = api_admin_beta_trust(decision=_decision("admin"), client=client)
    assert c2 == 200 and b2["trust"]["ask_degraded_rate"] == 0.2


def test_supabase_not_configured_returns_503(monkeypatch):
    # Force "no Supabase" shape so ``_build_rest_client`` returns None.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    code, body = api_admin_beta_users(decision=_decision("admin"), client=None)
    assert code == 503
    assert body["error"] == "supabase_not_configured"
