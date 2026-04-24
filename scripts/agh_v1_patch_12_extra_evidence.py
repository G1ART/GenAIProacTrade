#!/usr/bin/env python3
"""Patch 12 — auxiliary evidence JSONs (5 files beyond the runbook).

Emits:
  * patch_12_auth_flow_evidence.json       — signed JWT → auth/session → auth/me
  * patch_12_beta_allowlist_evidence.json  — invited/active/paused/revoked decisions
  * patch_12_event_taxonomy_evidence.json  — 13 allow + 3 reject samples + field drops
  * patch_12_telemetry_ingest_evidence.json— sliding-window rate limit boundary
  * patch_12_admin_surface_evidence.json   — admin role passes, beta_user = 403
"""

from __future__ import annotations

import json
import os
import sys
import uuid
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
    verify_user_is_active_beta,
)
from phase47_runtime.auth.guard import AuthDecision
from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests, verify_supabase_jwt
from phase47_runtime.routes_admin import api_admin_beta_users
from phase47_runtime.routes_auth import api_auth_me, api_auth_session
from phase47_runtime.routes_events import api_events_post
from phase47_runtime.telemetry.event_taxonomy import EVENT_TAXONOMY_V1
from phase47_runtime.telemetry.ingest import RateLimiter, TelemetryIngestor, sanitize_event


_OUT = _REPO_ROOT / "data" / "mvp" / "evidence"
_NOW = 1700000000
_SECRET = "evidence-jwt-secret"
_USER_UUID = "11111111-2222-3333-4444-555555555555"


class FakeRest:
    def __init__(self, rows: dict[str, list[dict[str, Any]]] | None = None):
        self._rows = rows or {}
        self.inserted: list[dict[str, Any]] = []

    def select(self, table, *, columns, filters=None, limit=None, order=None):
        return self._rows.get(table, [])

    def insert(self, table, rows, *, return_representation=False, on_conflict=None):
        self.inserted.extend([dict(r) for r in rows])
        return rows


def _write(name: str, obj: dict[str, Any]) -> Path:
    obj.setdefault("generated_utc", datetime.now(timezone.utc).isoformat())
    obj.setdefault("contract", "PATCH_12_EVIDENCE_V1")
    path = _OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")
    return path


def emit_auth_flow() -> dict[str, Any]:
    os.environ["SUPABASE_JWT_SECRET"] = _SECRET
    tok = sign_hs256_for_tests(
        {"sub": _USER_UUID, "email": "jane@example.com", "aud": "authenticated",
         "role": "authenticated", "iat": _NOW - 5, "exp": _NOW + 3600},
        secret=_SECRET,
    )
    # 1) verify
    v = verify_supabase_jwt(tok, secret=_SECRET, now_epoch=_NOW)
    # 2) POST /api/auth/session
    override = BetaAllowlistResult(ok=True, user_id=_USER_UUID, status="active",
                                   role="beta_user", mode=ALLOWLIST_MODE_ENFORCE)
    code1, body1 = api_auth_session(
        {"access_token": tok, "preferred_lang": "ko"},
        now_epoch=_NOW, allowlist_override=override,
    )
    # neutralize session id for stable evidence
    if body1.get("session_id"): body1["session_id"] = "<mint>"
    if body1.get("user"): body1["user"]["session_id"] = "<mint>"
    # 3) GET /api/auth/me
    decision = AuthDecision(
        ok=True, http_status=200, user_id=_USER_UUID,
        user_id_alias="bu_evidence0001", role="beta_user",
        allowlist_status="active", allowlist_mode="enforce",
        reason=None, claims={"sub": _USER_UUID},
    )
    code2, body2 = api_auth_me(decision=decision, rest_client=None)
    return {
        "jwt_verify": {"ok": v.ok, "reason": v.reason, "sub": v.claims and v.claims.get("sub")},
        "auth_session": {"http": code1, "body": body1},
        "auth_me":      {"http": code2, "body": body2},
    }


def emit_beta_allowlist() -> dict[str, Any]:
    class Rest:
        def __init__(self, rows): self.rows = rows
        def select(self, *a, **k): return self.rows

    cases = {}
    for status, ok_expected, reason_expected in (
        ("invited", True, None),
        ("active", True, None),
        ("paused", False, "allowlist_paused"),
        ("revoked", False, "allowlist_revoked"),
    ):
        from phase47_runtime.auth.beta_allowlist import clear_allowlist_cache
        clear_allowlist_cache()
        rows = [{"user_id": _USER_UUID, "status": status, "role": "beta_user"}]
        r = verify_user_is_active_beta(_USER_UUID, client=Rest(rows),
                                       mode_override=ALLOWLIST_MODE_ENFORCE)
        cases[status] = {"ok": r.ok, "reason": r.reason,
                         "ok_expected": ok_expected, "reason_expected": reason_expected,
                         "matches": r.ok == ok_expected and (r.reason == reason_expected)}
    return {"cases": cases, "all_matches": all(v["matches"] for v in cases.values())}


def emit_event_taxonomy() -> dict[str, Any]:
    allowlist_sample = []
    for name in sorted(EVENT_TAXONOMY_V1):
        ok, reason, row = sanitize_event(
            {"event_name": name, "session_id": str(uuid.uuid4()),
             "surface": "system", "lang": "ko"},
            user_id=_USER_UUID,
        )
        allowlist_sample.append({"event_name": name, "accepted": ok, "reason": reason})
    rejections = []
    for bad in ("steal_pii", "", "buy_stock_now"):
        ok, reason, _ = sanitize_event(
            {"event_name": bad, "session_id": str(uuid.uuid4()),
             "surface": "today", "lang": "ko"},
            user_id=_USER_UUID,
        )
        rejections.append({"input": bad, "accepted": ok, "reason": reason})
    field_drop = sanitize_event(
        {"event_name": "page_view", "session_id": str(uuid.uuid4()),
         "surface": "today", "lang": "ko",
         "metadata": {"intent": "explain_confidence", "raw_prompt": "SHOULD BE DROPPED"},
         "secret_top_level_field": "SHOULD BE DROPPED"},
        user_id=_USER_UUID,
    )
    return {
        "allowlist_sample": allowlist_sample,
        "rejections": rejections,
        "field_drop": {"accepted": field_drop[0], "row_keys": sorted(field_drop[2].keys()) if field_drop[2] else None,
                       "metadata_keys": sorted((field_drop[2] or {}).get("metadata", {}).keys())},
    }


def emit_telemetry_ingest() -> dict[str, Any]:
    rl = RateLimiter(max_events=100, window_seconds=60)
    fake = FakeRest()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    decision = AuthDecision(ok=True, http_status=200, user_id=_USER_UUID,
                            user_id_alias="bu_evidence0001", role="beta_user",
                            allowlist_status="active", allowlist_mode="enforce",
                            reason=None, claims=None)
    accepted = 0
    for _ in range(100):
        code, _ = api_events_post(
            {"event_name": "page_view", "session_id": str(uuid.uuid4()),
             "surface": "today", "lang": "ko"},
            decision=decision, ingestor=ing,
        )
        if code == 200: accepted += 1
    overflow_code, overflow_resp = api_events_post(
        {"event_name": "page_view", "session_id": str(uuid.uuid4()),
         "surface": "today", "lang": "ko"},
        decision=decision, ingestor=ing,
    )
    return {
        "max_events": 100, "window_seconds": 60,
        "accepted": accepted, "overflow_http": overflow_code,
        "overflow_reason": overflow_resp.get("reason"),
        "stored_rows": len(fake.inserted),
    }


def emit_admin_surface() -> dict[str, Any]:
    client = FakeRest({
        "beta_users_v1": [
            {"user_id": _USER_UUID, "email": "jane@example.com", "status": "active",
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
    beta_http, beta_body = api_admin_beta_users(decision=beta, client=client)
    admin_http, admin_body = api_admin_beta_users(decision=admin, client=client)
    return {
        "beta_user_access":  {"http": beta_http, "body": beta_body},
        "admin_access":      {"http": admin_http, "body": admin_body},
    }


def main() -> int:
    _write("patch_12_auth_flow_evidence.json",       emit_auth_flow())
    _write("patch_12_beta_allowlist_evidence.json",  emit_beta_allowlist())
    _write("patch_12_event_taxonomy_evidence.json",  emit_event_taxonomy())
    _write("patch_12_telemetry_ingest_evidence.json",emit_telemetry_ingest())
    _write("patch_12_admin_surface_evidence.json",   emit_admin_surface())
    print(json.dumps({"ok": True, "out_dir": str(_OUT), "evidence_emitted": 5}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
