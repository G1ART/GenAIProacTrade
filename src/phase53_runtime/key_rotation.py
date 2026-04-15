"""Per-source signing key rotation helpers (hashes at rest)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        s = str(ts).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def signing_keys_for_verification(source: dict[str, Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """
    Rows that may verify HMAC: active, next, and retired only during accept_previous_key_until grace.
    """
    now = now or datetime.now(timezone.utc)
    grace_until = _parse_iso(str(source.get("accept_previous_key_until") or ""))
    in_grace = grace_until is not None and now <= grace_until

    out: list[dict[str, Any]] = []
    for row in source.get("signing_keys") or []:
        kid = str(row.get("key_id") or "").strip()
        h = str(row.get("secret_hash") or "").strip().lower()
        if not kid or not h:
            continue
        st = str(row.get("status") or "active").strip().lower()
        if st == "active" or st == "next":
            out.append({"key_id": kid, "secret_hash": h, "status": st, "row": row})
            continue
        if st == "retired" and in_grace:
            out.append({"key_id": kid, "secret_hash": h, "status": st, "row": row})

    active_id = str(source.get("active_signing_key_id") or "").strip()
    out.sort(key=lambda x: (0 if x["key_id"] == active_id else 1, str(x["row"].get("created_at") or "")))
    return out


def source_requires_signed_ingress(source: dict[str, Any]) -> bool:
    if bool(source.get("signed_ingress_required")):
        return True
    for row in source.get("signing_keys") or []:
        st = str(row.get("status") or "").strip().lower()
        if st in ("active", "next"):
            return True
    return False
