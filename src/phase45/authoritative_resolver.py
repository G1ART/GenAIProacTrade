"""Phase 44 overrides Phase 43 legacy optimistic recommendation strings for current guidance."""

from __future__ import annotations

from typing import Any


def resolve_authoritative_recommendation(
    *,
    phase43_bundle: dict[str, Any],
    phase44_bundle: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic precedence: Phase 44 bundle (truthfulness + phase45 block) is authoritative.
    Phase 43 `phase44.*` nested recommendations are historical audit only.
    """
    p44_nested = phase43_bundle.get("phase44") or {}
    p44_truth = phase44_bundle.get("phase45") or {}

    auth_rec = str(
        p44_truth.get("phase45_recommendation")
        or "narrow_claims_document_proxy_limits_operator_closeout_v1"
    )
    auth_rationale = str(
        p44_truth.get("rationale")
        or "Phase 44 conservative cohort verdict (default if phase45 block missing)."
    )

    superseded: list[dict[str, Any]] = []
    leg = p44_nested.get("phase44_recommendation")
    if leg:
        superseded.append(
            {
                "source_artifact": "phase43_targeted_substrate_backfill_bundle",
                "field_path": "phase44.phase44_recommendation",
                "prior_value": leg,
                "prior_rationale": p44_nested.get("rationale"),
                "superseded_by_field": "phase44_claim_narrowing_truthfulness.phase45.phase45_recommendation",
            }
        )

    p42_r = phase43_bundle.get("phase42_rerun_after_backfill") or {}
    p43_in_p42 = (p42_r.get("phase43") or {}) if isinstance(p42_r, dict) else {}
    if p43_in_p42.get("phase43_recommendation"):
        superseded.append(
            {
                "source_artifact": "phase43_bundle.phase42_rerun_after_backfill.phase43",
                "field_path": "phase43_recommendation",
                "prior_value": p43_in_p42.get("phase43_recommendation"),
                "prior_rationale": p43_in_p42.get("rationale"),
                "superseded_by_field": "phase44_claim_narrowing_truthfulness (operator closeout layer)",
            }
        )

    return {
        "authoritative_phase": "phase44_claim_narrowing_truthfulness",
        "authoritative_recommendation": auth_rec,
        "authoritative_rationale": auth_rationale,
        "superseded_recommendations": superseded,
        "reason_for_precedence": (
            "Phase 44 separates provenance, rejects blank-field-only sector relabel as material "
            "falsifier improvement, narrows claims, and gates retry on named new paths. "
            "Phase 43 nested `phase44` used optimistic delta heuristics and must not surface as "
            "current operator guidance for this cohort."
        ),
    }
