"""AGH v1 Patch 5 — deterministic intent router (layer5_intent_router_v1) tests.

The Research Ask lane must not depend on a handful of substrings. The
router is deliberately deterministic, keyword-driven, and shared by both
the orchestrator's ``action_router_agent`` and the state reader's
per-kind collection profile so the same question always lands in the
same lane.

These tests guard:

    1. The priority ordering — most-specific (``sandbox_request``) wins
       over generic (``why_changed``) when both match.
    2. Korean + English phrasings both route as documented in the
       Patch 5 acceptance block.
    3. Unknown/ambiguous questions default to ``why_changed`` (safest
       fallback per Patch 5 workorder).
    4. ``USER_QUESTION_KINDS`` stays the single source of truth — every
       router output is a member of it.
"""

from __future__ import annotations

import pytest

from agentic_harness.agents.layer5_intent_router_v1 import (
    route_user_question_v1,
)
from agentic_harness.contracts.packets_v1 import USER_QUESTION_KINDS


@pytest.mark.parametrize(
    "question,expected",
    [
        # Sandbox requests (highest priority, research-driven action).
        ("재검증 돌려줘", "sandbox_request"),
        ("please rerun validation", "sandbox_request"),
        # Deeper rationale.
        ("이 해석의 근거가 뭐야?", "deeper_rationale"),
        ("give me the rationale", "deeper_rationale"),
        # What remains unproven.
        ("아직 증명되지 않은 건 뭐야?", "what_remains_unproven"),
        ("what is still unproven", "what_remains_unproven"),
        # What to watch.
        ("앞으로 지켜봐야 할 건?", "what_to_watch"),
        ("what should I watch next", "what_to_watch"),
        # System status.
        ("시스템 상태 알려줘", "system_status"),
        ("system health?", "system_status"),
        # Research pending.
        ("연구 대기 중인 거 있어?", "research_pending"),
        ("any research pending?", "research_pending"),
        # Why changed (fallback specific).
        ("왜 바뀌었어?", "why_changed"),
        ("why did this change", "why_changed"),
    ],
)
def test_router_classifies_representative_phrases(question, expected):
    assert route_user_question_v1(question) == expected


def test_router_defaults_to_why_changed_on_empty_or_unknown():
    assert route_user_question_v1("") == "why_changed"
    assert route_user_question_v1("zzzzzz") == "why_changed"


def test_router_priority_sandbox_beats_rationale_when_both_keywords_present():
    # "왜" (rationale) + "재검증" (sandbox) — sandbox must win because it is
    # the most specific + action-shaped intent.
    q = "왜 이게 바뀌었는지 + 재검증 한번 돌려줘"
    assert route_user_question_v1(q) == "sandbox_request"


def test_router_output_is_always_in_USER_QUESTION_KINDS_vocab():
    for q in [
        "재검증 해줘",
        "아직 증명되지 않",
        "앞으로 지켜",
        "status",
        "pending",
        "왜",
        "arbitrary",
    ]:
        assert route_user_question_v1(q) in USER_QUESTION_KINDS


def test_router_lang_argument_does_not_change_stable_intents():
    # Intent detection is keyword-based across ko/en; explicit lang must
    # not change the stable classification for unambiguous phrasings.
    assert (
        route_user_question_v1("rerun validation", lang="en")
        == route_user_question_v1("rerun validation", lang="ko")
        == "sandbox_request"
    )
