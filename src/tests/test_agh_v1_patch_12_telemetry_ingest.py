"""Patch 12 — telemetry ingest (sanitize + rate limit + batch)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from phase47_runtime.telemetry.ingest import (
    RateLimiter,
    TelemetryIngestor,
    sanitize_event,
)


class _FakeClient:
    def __init__(self) -> None:
        self.inserted: list[dict[str, Any]] = []

    def insert(self, table, rows, *, return_representation=False, on_conflict=None):
        assert table == "product_usage_events_v1"
        self.inserted.extend(rows)
        return rows


def _body(**over):
    base = {
        "event_name": "page_view",
        "session_id": str(uuid.uuid4()),
        "surface": "today",
        "lang": "ko",
    }
    base.update(over)
    return base


def test_single_event_accepted_and_stored():
    rl = RateLimiter(max_events=100, window_seconds=60)
    fake = _FakeClient()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    d = ing.ingest(_body(), user_id="u1")
    assert d.ok and d.http_status == 200 and d.stored
    assert len(fake.inserted) == 1


def test_rate_limit_exactly_at_boundary():
    rl = RateLimiter(max_events=3, window_seconds=60)
    fake = _FakeClient()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    for _ in range(3):
        d = ing.ingest(_body(), user_id="u1")
        assert d.ok
    over = ing.ingest(_body(), user_id="u1")
    assert not over.ok and over.http_status == 429 and over.reason == "rate_limited"


def test_rate_limit_per_user_isolated():
    rl = RateLimiter(max_events=2, window_seconds=60)
    ing = TelemetryIngestor(rest_client=_FakeClient(), rate_limiter=rl, telemetry_enabled=True)
    ing.ingest(_body(), user_id="u1"); ing.ingest(_body(), user_id="u1")
    assert not ing.ingest(_body(), user_id="u1").ok
    # u2 still has its own budget
    assert ing.ingest(_body(), user_id="u2").ok


def test_batch_accepts_multiple():
    rl = RateLimiter(max_events=50, window_seconds=60)
    fake = _FakeClient()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    body = {"events": [_body(event_name="session_started"), _body(event_name="page_view")]}
    d, accepted = ing.ingest_batch(body, user_id="u1")
    assert d.ok and len(accepted) == 2
    assert len(fake.inserted) == 2


def test_batch_rejects_if_one_event_bad():
    rl = RateLimiter(max_events=50, window_seconds=60)
    fake = _FakeClient()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=True)
    body = {"events": [_body(event_name="session_started"), _body(event_name="UNLISTED")]}
    d, accepted = ing.ingest_batch(body, user_id="u1")
    assert not d.ok and d.http_status == 400
    assert not accepted
    assert not fake.inserted


def test_batch_too_large_rejected():
    rl = RateLimiter(max_events=200, window_seconds=60)
    ing = TelemetryIngestor(rest_client=_FakeClient(), rate_limiter=rl, telemetry_enabled=True)
    body = {"events": [_body() for _ in range(TelemetryIngestor.BATCH_MAX + 1)]}
    d, _ = ing.ingest_batch(body, user_id="u1")
    assert not d.ok and d.reason == "batch_too_large"


def test_telemetry_disabled_still_returns_ok_but_not_stored():
    rl = RateLimiter(max_events=10, window_seconds=60)
    fake = _FakeClient()
    ing = TelemetryIngestor(rest_client=fake, rate_limiter=rl, telemetry_enabled=False)
    d = ing.ingest(_body(), user_id="u1")
    assert d.ok and not d.stored
    assert not fake.inserted


def test_sanitize_strips_unknown_top_level_fields():
    body = _body(secret_prompt="should be dropped")
    ok, reason, row = sanitize_event(body, user_id="u1")
    assert ok, reason
    assert "secret_prompt" not in row


def test_metadata_size_bounded():
    huge = {"intent": "x" * 5000}
    ok, reason, _ = sanitize_event(_body(metadata=huge), user_id="u1")
    # 5k chars for 'intent' > 256 → trimmed to 256, overall metadata still under cap
    assert ok  # trimmed, not rejected

    # But if we pack multiple allowed keys each at 256 chars we hit the 2KB cap
    # indirectly — simulate with strings containing only allowed fields.
    body = _body(metadata={k: "x" * 256 for k in ("intent", "source", "variant", "fallback", "dedupe_key")})
    ok2, reason2, _ = sanitize_event(body, user_id="u1")
    # 5 * ~265 bytes = ~1330 bytes < 2KB — still ok
    assert ok2


def test_auth_required_rejects_missing_user():
    from phase47_runtime.routes_events import api_events_post
    code, resp = api_events_post(_body(), decision=None)
    assert code == 401 and resp["error"] == "auth_required"
