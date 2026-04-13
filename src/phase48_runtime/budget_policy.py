"""Explicit budgets and stopping rules for the proactive loop."""

from __future__ import annotations

from typing import Any

BUDGET_CLASSES = frozenset(
    {
        "cheap_deterministic",
        "moderate_refresh",
        "bounded_debate",
        "premium_candidate_only",
    },
)


def default_budget_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "max_jobs_per_run": 5,
        "max_debate_turns": 3,
        "max_participating_roles": 5,
        "max_candidate_publishes_per_cycle": 3,
        "max_alerts_per_cycle": 2,
        "allowed_trigger_types": [
            "changed_artifact_bundle",
            "operator_research_signal",
            "closeout_reopen_candidate",
            "named_source_signal",
            "manual_watchlist",
        ],
        "stop_conditions": [
            "no_triggers_after_dedupe",
            "max_jobs_enqueued",
            "registry_write_ok",
        ],
        "notes": "No infinite loop: single orchestrator invocation = one bounded cycle.",
    }


def trigger_allowed(policy: dict[str, Any], trigger_type: str) -> bool:
    allowed = policy.get("allowed_trigger_types") or []
    if not allowed or allowed == ["*"]:
        return True
    return trigger_type in allowed
