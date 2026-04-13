"""Structured bounded disagreement — deterministic templates, explicit stop rules."""

from __future__ import annotations

from typing import Any

DEBATE_OUTCOMES = frozenset(
    {
        "supported",
        "unsupported",
        "unknown",
        "premium_required",
        "reopen_candidate",
        "no_action",
    },
)

DEFAULT_ROLES = (
    "signal_finder",
    "skeptical_reviewer",
    "management_decision_analyst",
    "premium_data_advocate",
    "operator_summarizer",
)


def _role_line(role: str, context: dict[str, Any]) -> str:
    auth = context.get("authoritative_recommendation") or "n/a"
    gate = context.get("primary_block_category") or "n/a"
    closeout = context.get("closeout_status") or "n/a"
    if role == "signal_finder":
        return (
            f"Under authoritative recommendation `{auth}`, I see no new dispositive public signal "
            "in the static bundle snapshot; watchpoints remain governance-bound."
        )
    if role == "skeptical_reviewer":
        return (
            f"Proxy-limited gate `{gate}` still caps falsifier strength; any urgency claim must "
            "stay subordinate to Phase 44 narrowing."
        )
    if role == "management_decision_analyst":
        return f"Closeout posture `{closeout}` implies hold until named path or new evidence; no auto-promotion."
    if role == "premium_data_advocate":
        return (
            "Premium paths are **candidates only** until ROI review; public substrate did not clear the blocker."
        )
    return (
        "Operator summary: bounded debate consumed bundle-only facts; escalate only via explicit candidate records."
    )


def run_bounded_debate(
    *,
    question: str,
    context: dict[str, Any],
    max_turns: int,
    max_roles: int,
) -> dict[str, Any]:
    max_turns = max(1, min(int(max_turns), 5))
    max_roles = max(1, min(int(max_roles), len(DEFAULT_ROLES)))
    roles = DEFAULT_ROLES[:max_roles]
    transcript: list[dict[str, Any]] = []
    turns_used = 0
    for turn in range(max_turns):
        for role in roles:
            transcript.append(
                {
                    "role": role,
                    "turn": turn,
                    "text": _role_line(role, context),
                }
            )
        turns_used = turn + 1
    outcome = _classify_outcome(context)
    return {
        "question": question,
        "max_turns_config": max_turns,
        "max_roles_config": max_roles,
        "turns_used": turns_used,
        "roles_used": list(roles),
        "transcript": transcript,
        "outcome": outcome,
        "stopped_reason": "policy_max_turns_reached",
        "governed": True,
    }


def _classify_outcome(context: dict[str, Any]) -> str:
    gate = str(context.get("gate_status") or "")
    block = str(context.get("primary_block_category") or "")
    closeout = str(context.get("closeout_status") or "")
    if "reopen" in str(context.get("debate_hint") or "").lower():
        return "reopen_candidate"
    if "premium" in str(context.get("debate_hint") or "").lower():
        return "premium_required"
    if "deferred" in gate and "proxy" in block:
        return "unknown"
    if closeout == "closed_pending_new_evidence":
        return "no_action"
    return "unsupported"


def debate_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "outcomes": sorted(DEBATE_OUTCOMES),
        "roles": list(DEFAULT_ROLES),
        "stopping_rules": ["max_turns", "max_roles", "single_cycle_only"],
    }
