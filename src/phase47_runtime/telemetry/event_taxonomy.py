"""Patch 12 — bounded event taxonomy for account-level telemetry.

The client is **never** allowed to invent new event names: any ingest
call with an ``event_name`` outside ``EVENT_TAXONOMY_V1`` is rejected
with 400. This keeps the telemetry schema bounded + audit-friendly and
prevents PII / free-form text from leaking into the events table.

The taxonomy is intentionally small and activation-oriented — it is the
minimum set needed to answer "is the private beta sticky?".
"""

from __future__ import annotations

from typing import Final


EVENT_TAXONOMY_V1: Final[frozenset[str]] = frozenset(
    {
        # activation + session lifecycle
        "session_started",
        "session_ended",
        "page_view",
        # product surfaces
        "research_opened",
        "replay_opened",
        "ask_opened",
        # Ask AI interactions
        "ask_quick_action_clicked",
        "ask_free_text_submitted",
        "ask_answer_rendered",
        "ask_degraded_shown",
        # trust + failure signals
        "sandbox_enqueue_clicked",
        "sandbox_request_blocked",
        # auth
        "auth_signout",
    }
)

ALLOWED_SURFACES: Final[frozenset[str]] = frozenset(
    {"today", "research", "replay", "ask_ai", "system", "auth", "admin"}
)

ALLOWED_HORIZON_KEYS: Final[frozenset[str]] = frozenset(
    {"short", "medium", "medium_long", "long"}
)

ALLOWED_LANGS: Final[frozenset[str]] = frozenset({"ko", "en"})

# Maximum size of the ``metadata`` JSON payload (bytes, post-sanitize).
MAX_METADATA_BYTES: Final[int] = 2048


def is_event_allowed(event_name: str) -> bool:
    return bool(event_name) and event_name in EVENT_TAXONOMY_V1


def is_surface_allowed(surface: str) -> bool:
    return bool(surface) and surface in ALLOWED_SURFACES


__all__ = [
    "ALLOWED_HORIZON_KEYS",
    "ALLOWED_LANGS",
    "ALLOWED_SURFACES",
    "EVENT_TAXONOMY_V1",
    "MAX_METADATA_BYTES",
    "is_event_allowed",
    "is_surface_allowed",
]
