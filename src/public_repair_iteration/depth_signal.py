"""Phase 22: operator-facing continuation signal for public-depth work (not premium gates)."""

from __future__ import annotations

from typing import Any

from public_repair_iteration.constants import ESCALATION_RECOMMENDATIONS
from public_repair_iteration.infra_noise import classify_infra_failure
from public_repair_iteration.marginal_policy import near_plateau_ledgers

PUBLIC_DEPTH_OPERATOR_SIGNALS = frozenset(
    {
        "continue_public_depth_buildout",
        "repeat_targeted_public_repair",
        "public_depth_near_plateau_review_required",
    }
)


def compute_public_depth_operator_signal(
    *,
    escalation_recommendation: str,
    depth_ledgers_newest_first: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """
    Deterministic signal layered on top of program escalation (Phase 20/21).

    depth_ledgers_newest_first: phase22_ledger dicts for public_depth members only, newest first.
    """
    esc = str(escalation_recommendation or "")
    if esc not in ESCALATION_RECOMMENDATIONS:
        esc = "hold_and_repeat_public_repair"
    rationale: dict[str, Any] = {"escalation_recommendation": esc}

    if not depth_ledgers_newest_first:
        rationale["rule"] = "no_public_depth_members_escalation_only"
        if esc == "continue_public_depth":
            return "continue_public_depth_buildout", rationale
        if esc == "open_targeted_premium_discovery":
            return "public_depth_near_plateau_review_required", rationale
        return "repeat_targeted_public_repair", rationale

    latest = depth_ledgers_newest_first[0]
    rationale["latest_improvement_classification"] = latest.get(
        "improvement_classification"
    )

    msg = str(latest.get("error_message") or "")
    if classify_infra_failure(msg):
        rationale["rule"] = "latest_depth_infra_noise_favor_repeat_repair_not_plateau"
        return "repeat_targeted_public_repair", rationale

    cls = str(latest.get("improvement_classification") or "")
    if cls == "meaningful_progress":
        rationale["rule"] = "latest_depth_meaningful_progress"
        return "continue_public_depth_buildout", rationale

    if esc == "open_targeted_premium_discovery":
        rationale["rule"] = "escalation_open_premium_operator_must_review_plateau_first"
        return "public_depth_near_plateau_review_required", rationale

    if near_plateau_ledgers(depth_ledgers_newest_first):
        rationale["rule"] = "repeated_shallow_or_flat_depth_moves"
        return "public_depth_near_plateau_review_required", rationale

    if esc == "continue_public_depth":
        rationale["rule"] = "escalation_continue_public_depth"
        return "continue_public_depth_buildout", rationale

    rationale["rule"] = "default_hold_maps_to_targeted_repair_cycle"
    return "repeat_targeted_public_repair", rationale


def assert_public_depth_operator_signal(value: str) -> str:
    if value not in PUBLIC_DEPTH_OPERATOR_SIGNALS:
        raise ValueError(f"invalid public depth operator signal: {value}")
    return value
