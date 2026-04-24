"""Patch 12 — ``/api/admin/beta/*`` read-only views for the /ops Beta Admin tab.

Security model:

* Caller **must** be authenticated (``AuthDecision.ok``).
* Caller **must** have ``role in {admin, internal}`` on ``beta_users_v1``.
  ``beta_user`` role gets 403. Graceful-downgrade (auth not configured)
  also gets 403 — admin surface requires real auth.
* We never return raw ``user_id`` UUIDs or raw email addresses in the
  DTO. User identity is aliased to ``bu_<sha256[:12]>``.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from phase47_runtime.auth.guard import AuthDecision, user_id_alias
from phase47_runtime.auth.supabase_rest import SupabaseRestClient, SupabaseRestError


_ADMIN_ROLES = frozenset({"admin", "internal"})


def _build_rest_client() -> Optional[SupabaseRestClient]:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return None
    return SupabaseRestClient(url=url, service_role_key=key)


def _require_admin(decision: Optional[AuthDecision]) -> Optional[tuple[int, dict[str, Any]]]:
    if decision is None or not decision.ok or not decision.user_id:
        return 401, {"ok": False, "error": "auth_required", "contract": "ADMIN_V1"}
    role = (decision.role or "").strip().lower()
    if role not in _ADMIN_ROLES:
        return 403, {"ok": False, "error": "admin_required", "contract": "ADMIN_V1"}
    return None


def _mask_email(email: str) -> str:
    s = (email or "").strip()
    if "@" not in s:
        return "••••"
    local, _, domain = s.partition("@")
    if not local:
        return "@" + domain
    head = local[:1]
    return f"{head}{'•' * max(1, len(local) - 1)}@{domain}"


def api_admin_beta_users(
    *,
    decision: Optional[AuthDecision],
    client: Optional[SupabaseRestClient] = None,
    query: Optional[dict[str, str]] = None,
) -> tuple[int, dict[str, Any]]:
    err = _require_admin(decision)
    if err is not None:
        return err
    c = client if client is not None else _build_rest_client()
    if c is None:
        return 503, {"ok": False, "error": "supabase_not_configured", "contract": "ADMIN_V1"}
    filters: dict[str, str] = {"limit": "200", "order": "invited_at.desc"}
    status_f = (query or {}).get("status") if query else None
    if status_f:
        filters["status"] = f"eq.{status_f}"
    try:
        rows = c.select(
            "beta_users_v1",
            columns="user_id,email,status,role,invited_at,activated_at",
            filters=filters,
        )
    except SupabaseRestError as exc:
        return exc.status or 502, {
            "ok": False,
            "error": "supabase_error",
            "status": exc.status,
            "contract": "ADMIN_V1",
        }
    items: list[dict[str, Any]] = []
    for r in rows:
        uid = str(r.get("user_id") or "")
        items.append(
            {
                "user_id_alias": user_id_alias(uid),
                "email_masked": _mask_email(str(r.get("email") or "")),
                "status": r.get("status"),
                "role": r.get("role"),
                "invited_at": r.get("invited_at"),
                "activated_at": r.get("activated_at"),
            }
        )
    return 200, {"ok": True, "items": items, "count": len(items), "contract": "ADMIN_V1"}


def api_admin_beta_sessions(
    *,
    decision: Optional[AuthDecision],
    client: Optional[SupabaseRestClient] = None,
) -> tuple[int, dict[str, Any]]:
    err = _require_admin(decision)
    if err is not None:
        return err
    c = client if client is not None else _build_rest_client()
    if c is None:
        return 503, {"ok": False, "error": "supabase_not_configured", "contract": "ADMIN_V1"}
    try:
        rows = c.select(
            "v_beta_sessions_recent_v1",
            columns="user_id,session_id,event_count,session_started_at,session_last_event_at,surfaces_touched",
            filters={"limit": "100"},
        )
    except SupabaseRestError as exc:
        return exc.status or 502, {
            "ok": False,
            "error": "supabase_error",
            "status": exc.status,
            "contract": "ADMIN_V1",
        }
    items: list[dict[str, Any]] = []
    for r in rows:
        uid = str(r.get("user_id") or "")
        items.append(
            {
                "user_id_alias": user_id_alias(uid),
                "session_id": r.get("session_id"),
                "event_count": r.get("event_count"),
                "session_started_at": r.get("session_started_at"),
                "session_last_event_at": r.get("session_last_event_at"),
                "surfaces_touched": r.get("surfaces_touched") or [],
            }
        )
    return 200, {"ok": True, "items": items, "count": len(items), "contract": "ADMIN_V1"}


def api_admin_beta_events(
    *,
    decision: Optional[AuthDecision],
    client: Optional[SupabaseRestClient] = None,
) -> tuple[int, dict[str, Any]]:
    err = _require_admin(decision)
    if err is not None:
        return err
    c = client if client is not None else _build_rest_client()
    if c is None:
        return 503, {"ok": False, "error": "supabase_not_configured", "contract": "ADMIN_V1"}
    try:
        rows = c.select(
            "v_beta_top_events_v1",
            columns="event_name,event_count,unique_users,unique_sessions",
            filters={"limit": "50"},
        )
    except SupabaseRestError as exc:
        return exc.status or 502, {
            "ok": False,
            "error": "supabase_error",
            "status": exc.status,
            "contract": "ADMIN_V1",
        }
    return 200, {"ok": True, "items": rows, "count": len(rows), "contract": "ADMIN_V1"}


def api_admin_beta_trust(
    *,
    decision: Optional[AuthDecision],
    client: Optional[SupabaseRestClient] = None,
) -> tuple[int, dict[str, Any]]:
    err = _require_admin(decision)
    if err is not None:
        return err
    c = client if client is not None else _build_rest_client()
    if c is None:
        return 503, {"ok": False, "error": "supabase_not_configured", "contract": "ADMIN_V1"}
    try:
        rows = c.select(
            "v_beta_trust_signals_v1",
            columns="total_ask_events,degraded_count,blocked_count,out_of_scope_count,ask_degraded_rate,out_of_scope_rate",
            filters={"limit": "1"},
        )
    except SupabaseRestError as exc:
        return exc.status or 502, {
            "ok": False,
            "error": "supabase_error",
            "status": exc.status,
            "contract": "ADMIN_V1",
        }
    payload = rows[0] if rows else {}
    return 200, {"ok": True, "trust": payload, "contract": "ADMIN_V1"}


__all__ = [
    "api_admin_beta_events",
    "api_admin_beta_sessions",
    "api_admin_beta_trust",
    "api_admin_beta_users",
]
