"""Explicit rerun / revision semantics for investigation memos (pure functions)."""

from __future__ import annotations

from typing import Any, Literal

MemoWriteMode = Literal["in_place_replace", "insert_new_version"]


def decide_memo_write_mode(
    *,
    payload_hash: str,
    generation_mode: str,
    latest_memo: dict[str, Any] | None,
    force_new_version: bool,
) -> MemoWriteMode:
    """
    Policy:
    - Same candidate, same payload_hash + same generation_mode, not forcing bump
      -> replace latest memo row in place (same memo_version / memo id).
    - Otherwise -> new memo_version = max+1 (append revision).
    """
    if force_new_version:
        return "insert_new_version"
    if latest_memo is None:
        return "insert_new_version"
    lh = latest_memo.get("input_payload_hash")
    lm = latest_memo.get("generation_mode")
    if lh == payload_hash and lm == generation_mode:
        return "in_place_replace"
    return "insert_new_version"


def resolve_queue_status_on_memo_regen(
    existing: dict[str, Any] | None,
    *,
    referee_passed: bool,
) -> str:
    """
    Queue status after memo write/regen:
    - reviewed / blocked_insufficient_data: preserved (memo_id still refreshed).
    - needs_followup: preserved (operator still owns follow-up).
    - otherwise: pending if referee passed, else needs_followup.
    """
    if not existing:
        return "pending" if referee_passed else "needs_followup"
    st = str(existing.get("status") or "pending")
    if st in ("reviewed", "needs_followup", "blocked_insufficient_data"):
        return st
    return "pending" if referee_passed else "needs_followup"


def assert_valid_queue_transition(
    from_status: str | None, to_status: str
) -> None:
    """Raises ValueError if target status is unknown (CLI guard)."""
    valid = (
        "pending",
        "reviewed",
        "needs_followup",
        "blocked_insufficient_data",
    )
    if to_status not in valid:
        raise ValueError(f"invalid queue status {to_status!r}; must be one of {valid}")
    _ = from_status  # reserved for stricter workflows later
