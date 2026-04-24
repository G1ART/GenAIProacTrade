#!/usr/bin/env python3
"""Patch 12 — private beta runbook (S1..S7 end-to-end).

Drives the seven Patch 12 invariants through pure-Python simulations (no
network). Each scenario must pass for the runbook to report ``all_ok``.

Scenarios:
  S1 — Valid JWT + invited allowlist row → /api/auth/session returns a
       bounded user DTO (alias, role, lang, session_id).
  S2 — Revoked allowlist row → auth guard returns 403.
  S3 — /api/events accepts an allowlisted event after sanitize.
  S4 — /api/events rejects an off-taxonomy event with 400.
  S5 — Rate limit: exactly N accept, N+1 returns 429.
  S6 — Admin surface: beta_user role = 403, admin role = 200 + alias-only.
  S7 — No-leak: no raw email / JWT secret / raw UUID appears in any DTO
       produced by scenarios S1..S6.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phase47_runtime.auth.beta_allowlist import (
    ALLOWLIST_MODE_ENFORCE,
    BetaAllowlistResult,
)
from phase47_runtime.auth.guard import AuthDecision, require_auth
from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests
from phase47_runtime.routes_admin import api_admin_beta_users
from phase47_runtime.routes_auth import api_auth_session
from phase47_runtime.routes_events import api_events_post
from phase47_runtime.telemetry.ingest import RateLimiter, TelemetryIngestor


_SECRET = "runbook-jwt-secret"
_USER_UUID = "11111111-2222-3333-4444-555555555555"
_USER_EMAIL = "runbook-user@example.com"


@dataclass
class FakeRest:
    rows_by_table: dict[str, list[dict[str, Any]]]
    inserted: list[tuple[str, list[dict[str, Any]]]]

    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.rows_by_table = rows_by_table or {}
        self.inserted = []

    def select(self, table, *, columns, filters=None, limit=None, order=None):
        return self.rows_by_table.get(table, [])

    def insert(self, table, rows, *, return_representation=False, on_conflict=None):
        rs = [dict(r) for r in rows]
        self.inserted.append((table, rs))
        return rs


def _now_int() -> int:
    return 1700000000  # deterministic epoch


def _valid_token(sub: str = _USER_UUID) -> str:
    now = _now_int()
    return sign_hs256_for_tests(
        {"sub": sub, "email": _USER_EMAIL, "aud": "authenticated",
         "role": "authenticated", "iat": now - 5, "exp": now + 3600},
        secret=_SECRET,
    )


def _scan_for_leaks(blob: Any) -> list[str]:
    """Look for raw PII / secret substrings anywhere in ``blob``."""

    text = json.dumps(blob, ensure_ascii=False)
    banned = [_USER_UUID, _USER_EMAIL, _SECRET]
    found = [b for b in banned if b in text]
    return found


def _s1_auth_session() -> dict[str, Any]:
    os.environ["SUPABASE_JWT_SECRET"] = _SECRET
    tok = _valid_token()
    override = BetaAllowlistResult(ok=True, user_id=_USER_UUID, status="active",
                                   role="beta_user", mode=ALLOWLIST_MODE_ENFORCE)
    code, body = api_auth_session(
        {"access_token": tok, "preferred_lang": "ko"},
        now_epoch=_now_int(),
        allowlist_override=override,
    )
    ok = code == 200 and body.get("ok") and body["user"]["user_id_alias"].startswith("bu_")
    return {"name": "S1_auth_session", "ok": ok, "http": code,
            "alias": body.get("user", {}).get("user_id_alias"),
            "leaks": _scan_for_leaks(body)}


def _s2_revoked_guard() -> dict[str, Any]:
    tok = _valid_token()
    os.environ["SUPABASE_JWT_SECRET"] = _SECRET

    def revoked(_uid=None, **_kw):
        return BetaAllowlistResult(ok=False, user_id=_USER_UUID, status="revoked",
                                   role="beta_user", mode=ALLOWLIST_MODE_ENFORCE,
                                   reason="allowlist_revoked")
    d = require_auth(method="GET", path="/api/product/today",
                     headers={"Authorization": f"Bearer {tok}"},
                     jwt_secret=_SECRET, allowlist=revoked, now_epoch=_now_int())
    ok = (not d.ok) and d.http_status == 403 and d.reason == "allowlist_revoked"
    return {"name": "S2_revoked_guard", "ok": ok,
            "http": d.http_status, "reason": d.reason,
            "leaks": _scan_for_leaks(d.to_error_payload())}


def _s3_valid_event_accepted() -> dict[str, Any]:
    rl = RateLimiter(max_events=100, window_seconds=60)
    fake = FakeRest()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    body = {
        "event_name": "ask_quick_action_clicked",
        "session_id": str(uuid.uuid4()),
        "surface": "ask_ai", "lang": "ko",
        "metadata": {"intent": "explain_confidence"},
    }
    decision = AuthDecision(ok=True, http_status=200, user_id=_USER_UUID,
                            user_id_alias="bu_runbook00001", role="beta_user",
                            allowlist_status="active", allowlist_mode="enforce",
                            reason=None, claims=None)
    code, resp = api_events_post(body, decision=decision, ingestor=ing)
    ok = code == 200 and resp.get("ok") and resp.get("stored")
    return {"name": "S3_event_accepted", "ok": ok, "http": code,
            "inserted_count": len(fake.inserted),
            "leaks": _scan_for_leaks(resp)}


def _s4_off_taxonomy_rejected() -> dict[str, Any]:
    rl = RateLimiter(max_events=100, window_seconds=60)
    fake = FakeRest()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    body = {"event_name": "steal_pii", "session_id": str(uuid.uuid4()),
            "surface": "system", "lang": "ko"}
    decision = AuthDecision(ok=True, http_status=200, user_id=_USER_UUID,
                            user_id_alias="bu_runbook00001", role="beta_user",
                            allowlist_status="active", allowlist_mode="enforce",
                            reason=None, claims=None)
    code, resp = api_events_post(body, decision=decision, ingestor=ing)
    ok = code == 400 and resp.get("reason") == "event_name_not_allowlisted"
    return {"name": "S4_off_taxonomy_rejected", "ok": ok, "http": code,
            "inserted_count": len(fake.inserted),
            "leaks": _scan_for_leaks(resp)}


def _s5_rate_limit_boundary() -> dict[str, Any]:
    rl = RateLimiter(max_events=5, window_seconds=60)
    fake = FakeRest()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    decision = AuthDecision(ok=True, http_status=200, user_id=_USER_UUID,
                            user_id_alias="bu_runbook00001", role="beta_user",
                            allowlist_status="active", allowlist_mode="enforce",
                            reason=None, claims=None)

    def ev():
        return {"event_name": "page_view", "session_id": str(uuid.uuid4()),
                "surface": "today", "lang": "ko"}
    accepted = 0
    last_code = 0
    for _ in range(5):
        code, _ = api_events_post(ev(), decision=decision, ingestor=ing)
        if code == 200: accepted += 1
        last_code = code
    code6, resp6 = api_events_post(ev(), decision=decision, ingestor=ing)
    ok = accepted == 5 and code6 == 429 and resp6.get("reason") == "rate_limited"
    return {"name": "S5_rate_limit_boundary", "ok": ok,
            "accepted_n": accepted, "overflow_http": code6}


def _s6_admin_rbac() -> dict[str, Any]:
    client = FakeRest(rows_by_table={
        "beta_users_v1": [
            {"user_id": _USER_UUID, "email": _USER_EMAIL, "status": "active",
             "role": "beta_user", "invited_at": "2026-04-20T00:00:00Z",
             "activated_at": "2026-04-20T01:00:00Z"},
        ],
    })
    beta = AuthDecision(ok=True, http_status=200, user_id="u-beta",
                       user_id_alias="bu_beta00000001", role="beta_user",
                       allowlist_status="active", allowlist_mode="enforce",
                       reason=None, claims=None)
    admin = AuthDecision(ok=True, http_status=200, user_id="u-admin",
                        user_id_alias="bu_admin00000001", role="admin",
                        allowlist_status="active", allowlist_mode="enforce",
                        reason=None, claims=None)
    c_beta, b_beta = api_admin_beta_users(decision=beta, client=client)
    c_admin, b_admin = api_admin_beta_users(decision=admin, client=client)
    ok = c_beta == 403 and c_admin == 200 and b_admin["items"][0]["user_id_alias"].startswith("bu_")
    return {"name": "S6_admin_rbac", "ok": ok,
            "beta_http": c_beta, "admin_http": c_admin,
            "admin_items": len(b_admin.get("items", [])),
            "leaks": _scan_for_leaks(b_admin)}


def _s7_aggregated_no_leak(results: list[dict[str, Any]]) -> dict[str, Any]:
    leaks: list[tuple[str, list[str]]] = []
    for r in results:
        found = r.get("leaks") or []
        if found:
            leaks.append((r["name"], found))
    ok = not leaks
    return {"name": "S7_aggregated_no_leak", "ok": ok, "leaks": leaks}


def main() -> int:
    scenarios = [_s1_auth_session(), _s2_revoked_guard(), _s3_valid_event_accepted(),
                 _s4_off_taxonomy_rejected(), _s5_rate_limit_boundary(), _s6_admin_rbac()]
    scenarios.append(_s7_aggregated_no_leak(scenarios))
    all_ok = all(s.get("ok") for s in scenarios)
    out = {
        "ok": True,
        "contract": "PATCH_12_PRIVATE_BETA_RUNBOOK_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "all_ok": all_ok,
        "scenarios": scenarios,
    }
    dest = _REPO_ROOT / "data" / "mvp" / "evidence" / "patch_12_private_beta_runbook_evidence.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")
    print(json.dumps({"all_ok": all_ok, "out": str(dest)}, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
