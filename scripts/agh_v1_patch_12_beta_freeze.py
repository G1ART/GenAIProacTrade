#!/usr/bin/env python3
"""Patch 12 — freeze script for the Private Beta surface.

Captures deterministic snapshots of:
  * /login.html + /login.css + /login.js + /auth_bootstrap.js (static)
  * auth DTOs (runtime-auth-config + auth/session + auth/me)
  * admin DTOs (beta_users, sessions, events, trust) rendered with fixtures
  * SHA256 manifest of every captured file

Outputs to ``data/mvp/evidence/screenshots_patch_12/``. Running the script
is idempotent — the timestamp in the manifest is the only volatile field,
and the per-file SHA256 digests form the "freeze".
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from phase47_runtime.auth.beta_allowlist import ALLOWLIST_MODE_ENFORCE, BetaAllowlistResult
from phase47_runtime.auth.guard import AuthDecision
from phase47_runtime.auth.jwt_verifier import sign_hs256_for_tests
from phase47_runtime.routes_admin import (
    api_admin_beta_events,
    api_admin_beta_sessions,
    api_admin_beta_trust,
    api_admin_beta_users,
)
from phase47_runtime.routes_auth import (
    api_auth_me,
    api_auth_session,
    api_runtime_auth_config,
)


_OUT_DIR = _REPO_ROOT / "data" / "mvp" / "evidence" / "screenshots_patch_12"
_STATIC = _SRC / "phase47_runtime" / "static"
_STATIC_FILES = ["login.html", "login.css", "login.js", "auth_bootstrap.js", "ops_admin.js"]


@dataclass
class FakeRest:
    rows_by_table: dict[str, list[dict[str, Any]]]

    def select(self, table, *, columns, filters=None, limit=None, order=None):
        return self.rows_by_table.get(table, [])

    def insert(self, *a, **k):
        return []


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256(data)


def _freeze_static(manifest: dict[str, str]) -> None:
    for name in _STATIC_FILES:
        src = _STATIC / name
        dst = _OUT_DIR / "static" / name
        raw = src.read_bytes()
        _write(dst, raw)
        manifest[f"static/{name}"] = _sha256(raw)


def _dto_auth_config() -> dict[str, Any]:
    os.environ.setdefault("SUPABASE_URL", "https://example-freeze.supabase.co")
    os.environ.setdefault("SUPABASE_ANON_KEY", "anon-public-key-placeholder")
    code, body = api_runtime_auth_config()
    return {"http_status": code, "body": body}


def _dto_auth_session() -> dict[str, Any]:
    secret = "freeze-jwt-secret"
    os.environ["SUPABASE_JWT_SECRET"] = secret
    now = 1700000000
    payload = {
        "sub": "11111111-2222-3333-4444-555555555555",
        "email": "jane@example.com",
        "aud": "authenticated", "role": "authenticated",
        "iat": now - 5, "exp": now + 3600,
    }
    tok = sign_hs256_for_tests(payload, secret=secret)
    override = BetaAllowlistResult(ok=True, user_id=payload["sub"], status="active",
                                   role="beta_user", mode=ALLOWLIST_MODE_ENFORCE)
    code, body = api_auth_session(
        {"access_token": tok, "preferred_lang": "ko", "display_name": "Jane"},
        now_epoch=now,
        allowlist_override=override,
    )
    # replace volatile session_id with deterministic placeholder for freeze
    if isinstance(body.get("session_id"), str):
        body["session_id"] = "<volatile-session-id>"
    if isinstance(body.get("user"), dict) and body["user"].get("session_id"):
        body["user"]["session_id"] = "<volatile-session-id>"
    return {"http_status": code, "body": body}


def _dto_auth_me() -> dict[str, Any]:
    decision = AuthDecision(
        ok=True, http_status=200,
        user_id="11111111-2222-3333-4444-555555555555",
        user_id_alias="bu_freezealias0",
        role="beta_user", allowlist_status="active", allowlist_mode="enforce",
        reason=None, claims={"sub": "11111111-2222-3333-4444-555555555555"},
    )
    code, body = api_auth_me(decision=decision, rest_client=None)
    return {"http_status": code, "body": body}


def _dto_admin_users() -> dict[str, Any]:
    client = FakeRest(rows_by_table={
        "beta_users_v1": [
            {"user_id": "u-admin", "email": "admin@metis.ai", "status": "active", "role": "admin",
             "invited_at": "2026-04-20T00:00:00Z", "activated_at": "2026-04-20T00:10:00Z"},
            {"user_id": "u-user1", "email": "user1@example.com", "status": "active", "role": "beta_user",
             "invited_at": "2026-04-22T00:00:00Z", "activated_at": "2026-04-22T08:00:00Z"},
            {"user_id": "u-user2", "email": "user2@example.com", "status": "invited", "role": "beta_user",
             "invited_at": "2026-04-23T00:00:00Z", "activated_at": None},
        ],
    })
    d = AuthDecision(ok=True, http_status=200, user_id="u-admin",
                     user_id_alias="bu_adminfreez1", role="admin",
                     allowlist_status="active", allowlist_mode="enforce",
                     reason=None, claims=None)
    code, body = api_admin_beta_users(decision=d, client=client)
    return {"http_status": code, "body": body}


def _dto_admin_sessions() -> dict[str, Any]:
    client = FakeRest(rows_by_table={
        "v_beta_sessions_recent_v1": [
            {"user_id": "u-user1", "session_id": "s-1", "event_count": 12,
             "session_started_at": "2026-04-23T08:10:00Z",
             "session_last_event_at": "2026-04-23T08:45:00Z",
             "surfaces_touched": ["today", "research", "ask_ai"]},
        ],
    })
    d = AuthDecision(ok=True, http_status=200, user_id="u-admin",
                     user_id_alias="bu_adminfreez1", role="admin",
                     allowlist_status="active", allowlist_mode="enforce",
                     reason=None, claims=None)
    code, body = api_admin_beta_sessions(decision=d, client=client)
    return {"http_status": code, "body": body}


def _dto_admin_events() -> dict[str, Any]:
    client = FakeRest(rows_by_table={
        "v_beta_top_events_v1": [
            {"event_name": "page_view", "event_count": 83, "unique_users": 5, "unique_sessions": 12},
            {"event_name": "ask_quick_action_clicked", "event_count": 27, "unique_users": 4, "unique_sessions": 9},
            {"event_name": "research_opened", "event_count": 18, "unique_users": 4, "unique_sessions": 8},
        ],
    })
    d = AuthDecision(ok=True, http_status=200, user_id="u-admin",
                     user_id_alias="bu_adminfreez1", role="admin",
                     allowlist_status="active", allowlist_mode="enforce",
                     reason=None, claims=None)
    code, body = api_admin_beta_events(decision=d, client=client)
    return {"http_status": code, "body": body}


def _dto_admin_trust() -> dict[str, Any]:
    client = FakeRest(rows_by_table={
        "v_beta_trust_signals_v1": [
            {"total_ask_events": 40, "degraded_count": 5, "blocked_count": 1,
             "out_of_scope_count": 3, "ask_degraded_rate": 0.125, "out_of_scope_rate": 0.075},
        ],
    })
    d = AuthDecision(ok=True, http_status=200, user_id="u-admin",
                     user_id_alias="bu_adminfreez1", role="admin",
                     allowlist_status="active", allowlist_mode="enforce",
                     reason=None, claims=None)
    code, body = api_admin_beta_trust(decision=d, client=client)
    return {"http_status": code, "body": body}


def _freeze_dtos(manifest: dict[str, str]) -> None:
    mapping = {
        "dtos/auth_config.json":   _dto_auth_config(),
        "dtos/auth_session.json":  _dto_auth_session(),
        "dtos/auth_me.json":       _dto_auth_me(),
        "dtos/admin_users.json":   _dto_admin_users(),
        "dtos/admin_sessions.json":_dto_admin_sessions(),
        "dtos/admin_events.json":  _dto_admin_events(),
        "dtos/admin_trust.json":   _dto_admin_trust(),
    }
    for rel, dto in mapping.items():
        raw = json.dumps(dto, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
        _write(_OUT_DIR / rel, raw)
        manifest[rel] = _sha256(raw)


def main() -> int:
    manifest: dict[str, str] = {}
    _freeze_static(manifest)
    _freeze_dtos(manifest)
    captured_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "ok": True,
        "contract": "PATCH_12_BETA_FREEZE_V1",
        "captured_at_utc": captured_at,
        "file_count": len(manifest),
        "sha256_manifest": manifest,
    }
    _write(_OUT_DIR / "MANIFEST.json",
           json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    print(json.dumps({"ok": True, "out_dir": str(_OUT_DIR), "files": len(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
