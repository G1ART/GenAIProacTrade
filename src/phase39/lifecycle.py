"""Hypothesis lifecycle transitions with append-only audit (no silent overwrites)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _ensure_transition_log(h: dict[str, Any]) -> list[dict[str, Any]]:
    log = h.get("lifecycle_transitions")
    if not isinstance(log, list):
        log = []
        h["lifecycle_transitions"] = log
    return log


def apply_lifecycle_transition(
    hypothesis: dict[str, Any],
    *,
    to_status: str,
    reason: str,
    evidence_ref: str,
    transitioned_utc: str | None = None,
) -> dict[str, Any]:
    ts = transitioned_utc or datetime.now(timezone.utc).isoformat()
    log = _ensure_transition_log(hypothesis)
    from_status = str(hypothesis.get("status") or "")
    log.append(
        {
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
            "evidence_ref": evidence_ref,
            "transitioned_utc": ts,
        }
    )
    hypothesis["status"] = to_status
    return hypothesis


def normalize_hypothesis_lifecycle_fields(h: dict[str, Any]) -> dict[str, Any]:
    if "lifecycle_transitions" not in h or not isinstance(h.get("lifecycle_transitions"), list):
        h["lifecycle_transitions"] = []
    return h
