"""Patch 12 — event_taxonomy allowlist + sanitize contract."""

from __future__ import annotations

import uuid

from phase47_runtime.telemetry.event_taxonomy import (
    ALLOWED_HORIZON_KEYS,
    ALLOWED_LANGS,
    ALLOWED_SURFACES,
    EVENT_TAXONOMY_V1,
    is_event_allowed,
    is_surface_allowed,
)
from phase47_runtime.telemetry.ingest import sanitize_event


def _body(**over):
    base = {
        "event_name": "page_view",
        "session_id": str(uuid.uuid4()),
        "surface": "today",
        "lang": "ko",
    }
    base.update(over)
    return base


def test_taxonomy_has_exactly_thirteen_events():
    assert len(EVENT_TAXONOMY_V1) == 13


def test_required_events_present():
    for name in (
        "session_started", "page_view", "research_opened", "replay_opened",
        "ask_opened", "ask_quick_action_clicked", "ask_free_text_submitted",
        "ask_answer_rendered", "ask_degraded_shown",
        "sandbox_enqueue_clicked", "sandbox_request_blocked", "auth_signout",
    ):
        assert is_event_allowed(name), name


def test_arbitrary_event_rejected():
    ok, reason, row = sanitize_event(_body(event_name="steal_pii"), user_id="u1")
    assert not ok and reason == "event_name_not_allowlisted"


def test_unknown_metadata_keys_dropped():
    ok, reason, row = sanitize_event(
        _body(metadata={"intent": "explain_confidence", "raw_prompt": "leak me"}),
        user_id="u1",
    )
    assert ok, reason
    assert row["metadata"] == {"intent": "explain_confidence"}


def test_bad_session_id_rejected():
    ok, reason, row = sanitize_event(_body(session_id="not-a-uuid"), user_id="u1")
    assert not ok and reason == "invalid_session_id"


def test_bad_surface_rejected():
    ok, reason, row = sanitize_event(_body(surface="buy_now"), user_id="u1")
    assert not ok and reason == "surface_not_allowlisted"


def test_bad_horizon_rejected():
    ok, reason, row = sanitize_event(_body(horizon_key="weekly"), user_id="u1")
    assert not ok and reason == "invalid_horizon_key"


def test_bad_lang_rejected():
    ok, reason, row = sanitize_event(_body(lang="fr"), user_id="u1")
    assert not ok and reason == "invalid_lang"


def test_surface_set_is_stable():
    assert ALLOWED_SURFACES == frozenset({"today", "research", "replay", "ask_ai", "system", "auth", "admin"})
    assert ALLOWED_HORIZON_KEYS == frozenset({"short", "medium", "medium_long", "long"})
    assert ALLOWED_LANGS == frozenset({"ko", "en"})


def test_surface_allowlist_helper():
    assert is_surface_allowed("today")
    assert not is_surface_allowed("billing")
