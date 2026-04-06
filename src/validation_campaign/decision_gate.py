from __future__ import annotations

from typing import Any

from validation_campaign.constants import STRATEGIC_RECOMMENDATIONS


def decide_strategic_recommendation(metrics: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """
    Single bounded recommendation from campaign aggregates.
    Order: insufficient evidence → premium seam → public depth (default tilt).
    """
    n_eligible = int(metrics.get("n_eligible") or 0)
    n_validated = int(metrics.get("n_validated") or 0)
    dominant_qc = str(metrics.get("dominant_program_quality_class") or "unknown")

    if n_eligible < 2:
        return "insufficient_evidence_repeat_campaign", {
            "rule": "min_eligible_hypotheses",
            "threshold": 2,
            "n_eligible": n_eligible,
        }

    if n_validated < 2:
        return "insufficient_evidence_repeat_campaign", {
            "rule": "min_validated_hypotheses",
            "threshold": 2,
            "n_validated": n_validated,
        }

    strong_usable_members = int(metrics.get("n_members_strong_or_usable_context") or 0)
    total_failures = int(metrics.get("total_failure_cases_across_members") or 0)
    contra = int(metrics.get("n_contradictory_failure_cases") or 0)
    premium_nonempty = int(metrics.get("n_failure_cases_with_nonempty_premium_hint") or 0)
    thin_fail_share = float(metrics.get("thin_input_failure_share") or 0.0)
    degraded_fail_share = float(metrics.get("degraded_or_failed_context_failure_share") or 0.0)

    min_strong_floor = max(2, (n_validated + 1) // 2)
    if strong_usable_members >= min_strong_floor and total_failures > 0:
        premium_signal = contra + premium_nonempty
        premium_share = premium_signal / total_failures
        if premium_share >= 0.35 and contra >= 1:
            return "targeted_premium_seam_first", {
                "rule": "premium_dominated_in_good_substrate",
                "strong_usable_members": strong_usable_members,
                "premium_signal_cases": premium_signal,
                "total_failure_cases": total_failures,
                "premium_share": round(premium_share, 4),
            }

    thin_degraded = thin_fail_share + degraded_fail_share
    if dominant_qc in ("thin_input", "failed", "degraded", "unknown") or thin_degraded >= 0.35:
        return "public_data_depth_first", {
            "rule": "thin_or_degraded_failure_dominance_or_program_qc",
            "dominant_program_quality_class": dominant_qc,
            "thin_input_failure_share": thin_fail_share,
            "degraded_context_failure_share": degraded_fail_share,
        }

    if n_validated < n_eligible and n_validated <= 2:
        return "insufficient_evidence_repeat_campaign", {
            "rule": "sparse_validation_coverage",
            "n_validated": n_validated,
            "n_eligible": n_eligible,
        }

    return "public_data_depth_first", {
        "rule": "default_public_substrate_first",
        "dominant_program_quality_class": dominant_qc,
        "note": "No premium-contradiction cluster in strong substrate; deepen public evidence first.",
    }


def assert_bounded_recommendation(value: str) -> str:
    if value not in STRATEGIC_RECOMMENDATIONS:
        raise ValueError(f"invalid strategic recommendation: {value}")
    return value
