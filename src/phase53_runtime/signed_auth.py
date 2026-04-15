"""HMAC-signed body verification (Phase 53)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

from phase52_runtime.webhook_auth import verify_webhook_secret

from phase53_runtime.key_rotation import signing_keys_for_verification, source_requires_signed_ingress


def canonical_signing_string(*, timestamp: str, nonce: str, source_id: str, raw_body: bytes) -> str:
    body_digest = hashlib.sha256(raw_body).hexdigest()
    return f"v1|{timestamp}|{nonce}|{source_id}|{body_digest}"


def signature_tuple_digest(*, timestamp: str, nonce: str, source_id: str, raw_body: bytes) -> str:
    c = canonical_signing_string(timestamp=timestamp, nonce=nonce, source_id=source_id, raw_body=raw_body)
    return hashlib.sha256(c.encode("utf-8")).hexdigest()


def compute_hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac_hex(*, presented: str, secret: str, message: str) -> bool:
    exp = compute_hmac_hex(secret, message)
    return secrets.compare_digest(exp.lower(), str(presented or "").strip().lower())


def _parse_ts(ts: str) -> datetime | None:
    try:
        s = str(ts).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def verify_timestamp_freshness(ts_header: str, *, now: datetime, max_skew_sec: int = 300) -> tuple[bool, str]:
    dt = _parse_ts(ts_header)
    if dt is None:
        return False, "invalid_timestamp_format"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = abs((now - dt).total_seconds())
    if delta > max_skew_sec:
        return False, "stale_timestamp"
    return True, "ok"


def verify_signed_request(
    source: dict[str, Any],
    *,
    raw_body: bytes,
    source_id: str,
    timestamp_header: str,
    signature_header: str,
    nonce_header: str | None,
    presented_plain_secret: str,
    now: datetime | None = None,
) -> tuple[bool, str, str | None]:
    """
    If source requires signed ingress: verify timestamp, nonce usage (caller registers after),
    HMAC against one of the signing key secret **presentations** — at rest we only store hashes.

    Because we only store `secret_hash` for signing keys (like shared_secret), the caller must
    pass the raw signing secret out-of-band for verification (same model as X-Webhook-Secret).

    Contract: signing key rows use `secret_hash` = SHA-256(raw_signing_secret). The HTTP layer
    passes the raw signing secret in `X-Webhook-Signing-Secret` (optional) when using rotated keys,
    OR reuses `X-Webhook-Secret` when `signing_secret_header` is not set (tests use same header).

    For this implementation: try `presented_plain_secret` against each key's `secret_hash` via
    verify_webhook_secret, then HMAC with the **raw** secret presented (the same string).
    """
    now = now or datetime.now(timezone.utc)
    if not source_requires_signed_ingress(source):
        return True, "signed_not_required", None

    ok_ts, ts_reason = verify_timestamp_freshness(timestamp_header, now=now)
    if not ok_ts:
        return False, ts_reason, None

    nonce = str(nonce_header or "").strip()
    if not nonce:
        return False, "missing_nonce", None

    canonical = canonical_signing_string(timestamp=timestamp_header, nonce=nonce, source_id=source_id, raw_body=raw_body)
    if not signature_header:
        return False, "missing_signature", None

    keys = signing_keys_for_verification(source, now=now)
    if not keys:
        return False, "no_signing_keys_configured", None

    for row in keys:
        h = row["secret_hash"]
        if not verify_webhook_secret(stored_hash=h, presented_secret=presented_plain_secret):
            continue
        if verify_hmac_hex(presented=str(signature_header), secret=presented_plain_secret, message=canonical):
            return True, "ok", row["key_id"]
        return False, "bad_signature", row["key_id"]

    return False, "signing_secret_mismatch", None
