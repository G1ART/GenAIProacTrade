"""Deterministic post-patch continuation chooser (repair vs depth vs verify vs plateau hold)."""

from __future__ import annotations

from typing import Any, Literal

from public_repair_iteration.depth_iteration import export_public_depth_series_brief
from public_repair_iteration.depth_signal import compute_public_depth_operator_signal
from public_repair_iteration.service import compute_public_repair_plateau

PostPatchAction = Literal[
    "verify_only",
    "advance_repair_series",
    "advance_public_depth_iteration",
    "hold_for_plateau_review",
]


def choose_post_patch_next_action_from_signals(
    *,
    escalation_recommendation: str,
    depth_operator_signal: str,
    verify_only: bool = False,
) -> dict[str, Any]:
    """
    Pure decision helper for tests — maps escalation + depth signal → action + rationale text.
    """
    esc = str(escalation_recommendation or "")
    sig = str(depth_operator_signal or "")
    if verify_only:
        return {
            "action": "verify_only",
            "reason": "verify_only_flag_set",
            "escalation_recommendation": esc,
            "depth_operator_signal": sig,
        }
    if esc == "open_targeted_premium_discovery":
        return {
            "action": "hold_for_plateau_review",
            "reason": "escalation_premium_discovery_requires_human_review_no_auto_advance",
            "escalation_recommendation": esc,
            "depth_operator_signal": sig,
        }
    if sig == "public_depth_near_plateau_review_required":
        return {
            "action": "hold_for_plateau_review",
            "reason": "depth_operator_signal_near_plateau_review",
            "escalation_recommendation": esc,
            "depth_operator_signal": sig,
        }
    if sig == "continue_public_depth_buildout":
        return {
            "action": "advance_public_depth_iteration",
            "reason": "depth_signal_continue_public_depth_buildout",
            "escalation_recommendation": esc,
            "depth_operator_signal": sig,
        }
    if sig == "repeat_targeted_public_repair":
        return {
            "action": "advance_repair_series",
            "reason": "depth_signal_repeat_targeted_public_repair",
            "escalation_recommendation": esc,
            "depth_operator_signal": sig,
        }
    return {
        "action": "advance_public_depth_iteration",
        "reason": "default_public_first_safe_fallback",
        "escalation_recommendation": esc,
        "depth_operator_signal": sig,
    }


def choose_post_patch_next_action(
    client: Any,
    *,
    series_id: str,
    verify_only: bool = False,
) -> dict[str, Any]:
    """Fetch plateau + depth brief; compute operator signal; delegate to pure chooser."""
    plateau = compute_public_repair_plateau(client, series_id=series_id)
    esc = str(plateau.get("escalation_recommendation") or "")
    brief = export_public_depth_series_brief(client, series_id=series_id)
    ledgers = brief.get("depth_ledgers_newest_first") or []
    if not isinstance(ledgers, list):
        ledgers = []
    sig, sig_rationale = compute_public_depth_operator_signal(
        escalation_recommendation=esc,
        depth_ledgers_newest_first=ledgers,
    )
    base = choose_post_patch_next_action_from_signals(
        escalation_recommendation=esc,
        depth_operator_signal=sig,
        verify_only=verify_only,
    )
    return {
        **base,
        "plateau_ok": bool(plateau.get("ok")),
        "depth_brief_ok": bool(brief.get("ok")),
        "signal_rationale": sig_rationale,
        "plateau_metrics": plateau.get("plateau_metrics"),
    }
