"""Shared-secret verification (hash-at-rest, timing-safe compare)."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any


def hash_shared_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_webhook_secret(*, stored_hash: str, presented_secret: str) -> bool:
    """
    `stored_hash` is sha256 hex (64 chars). `presented_secret` is raw secret from header.
    """
    if not stored_hash or not presented_secret:
        return False
    digest = hashlib.sha256(presented_secret.encode("utf-8")).hexdigest()
    return secrets.compare_digest(digest.encode("ascii"), str(stored_hash).strip().lower().encode("ascii"))


def source_requires_auth(source: dict[str, Any]) -> bool:
    return bool(str(source.get("shared_secret_hash") or "").strip())


def verify_source_auth(
    source: dict[str, Any],
    *,
    presented_secret: str,
) -> tuple[bool, str]:
    if not source.get("enabled", True):
        return False, "source_disabled"
    h = str(source.get("shared_secret_hash") or "").strip()
    if not h:
        return False, "source_missing_secret_hash"
    if not verify_webhook_secret(stored_hash=h, presented_secret=presented_secret):
        return False, "invalid_webhook_secret"
    return True, "ok"
