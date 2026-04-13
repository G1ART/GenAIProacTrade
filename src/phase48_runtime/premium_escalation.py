"""Premium escalation as **candidate** only — never a forced purchase action."""

from __future__ import annotations

from typing import Any


def evaluate_premium_candidate(
    *,
    debate_outcome: str,
    gate_status: str,
    primary_block_category: str,
    founder_uncertainties: list[Any],
    debate_transcript_len: int,
) -> dict[str, Any]:
    blocker_persists = "deferred" in str(gate_status).lower() or bool(primary_block_category)
    uncertainty_matters = len(founder_uncertainties or []) > 0
    debate_saw_roles = debate_transcript_len > 0

    premium_candidate = (
        blocker_persists
        and uncertainty_matters
        and debate_outcome in ("unknown", "premium_required", "unsupported")
        and debate_saw_roles
    )

    named_path = "vendor_or_internal_dataset_capable_of_sector_or_strict_pit_enrichment"
    reduction = (
        "Could narrow proxy-limited falsifier gap if it yields sector_available or strict filing-public picks "
        "under governance — **expected reduction qualitative, not guaranteed**."
    )

    return {
        "premium_candidate": premium_candidate,
        "justification": (
            "Public bundle still shows deferred/proxy-limited substrate; uncertainties affect claim posture. "
            "Premium is proposed only as an ROI-gated candidate."
            if premium_candidate
            else "No premium candidate: either uncertainties are low or debate outcome does not justify cost."
        ),
        "candidate_data_type": named_path if premium_candidate else "",
        "affected_assets": [],
        "expected_reduction_in_uncertainty": reduction if premium_candidate else "n/a",
        "not_forced_into_surface_without_review": True,
    }
