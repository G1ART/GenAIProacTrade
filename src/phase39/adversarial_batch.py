"""Phase 39 multi-stance reviews — append-only; preserve original lineage auditor record."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from phase37.adversarial_review import CritiqueCategory, DecisionImpact, ReviewerStance

PRIMARY_HYPOTHESIS_ID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"
ORIGINAL_REVIEW_ID_PLACEHOLDER = "17b65b06-5001-401a-be26-25064897af17"


def phase39_additional_reviews(
    *,
    lineage_auditor_review_id: str,
    transitioned_utc: str | None = None,
) -> list[dict[str, Any]]:
    ts = transitioned_utc or datetime.now(timezone.utc).isoformat()
    rid_lineage = lineage_auditor_review_id or ORIGINAL_REVIEW_ID_PLACEHOLDER

    return [
        {
            "review_id": str(uuid4()),
            "hypothesis_id": PRIMARY_HYPOTHESIS_ID,
            "reviewer_stance": ReviewerStance.SKEPTICAL_FUNDAMENTAL.value,
            "critique_category": CritiqueCategory.THESIS.value,
            "challenge_text": (
                "The eight names may be undergoing real strategic or accounting transitions; treating residual "
                "join mismatch as a pure timestamp artifact risks understating fundamental state uncertainty."
            ),
            "decision_impact": DecisionImpact.DOWNGRADE_CONFIDENCE.value,
            "resolution": "deferred",
            "resolution_notes": (
                "Requires cross-family tests (cadence, filing boundary) before treating mismatch as mechanical only."
            ),
            "created_utc": ts,
            "resolution_dependency_review_ids": [rid_lineage],
            "explicit_impact": "blocks_narrative_overclaim_until_fundamental_overlap_cleared",
            "phase39_batch": True,
        },
        {
            "review_id": str(uuid4()),
            "hypothesis_id": PRIMARY_HYPOTHESIS_ID,
            "reviewer_stance": ReviewerStance.SKEPTICAL_QUANT.value,
            "critique_category": CritiqueCategory.DATA.value,
            "challenge_text": (
                "A single PIT harness with three specs is underpowered for quantifying publication lag vs grid "
                "effects; alternate runs may be too correlated to isolate cadence from run-id effects."
            ),
            "decision_impact": DecisionImpact.REQUIRE_EXTRA_TEST.value,
            "resolution": "deferred",
            "resolution_notes": (
                "Bind additional spec families (Phase 39 contract) and require row-level comparisons under shared schema."
            ),
            "created_utc": ts,
            "resolution_dependency_review_ids": [rid_lineage],
            "explicit_impact": "requires_pit_family_binding_before_promotion_review",
            "phase39_batch": True,
        },
        {
            "review_id": str(uuid4()),
            "hypothesis_id": PRIMARY_HYPOTHESIS_ID,
            "reviewer_stance": ReviewerStance.REGIME_HORIZON_REVIEWER.value,
            "critique_category": CritiqueCategory.HORIZON_MISMATCH.value,
            "challenge_text": (
                "Fixture analysis is 1y-leaning while sector/cadence mechanisms may operate on 3–5y reporting "
                "regimes; promotion or product use without horizon alignment misstates residual severity."
            ),
            "decision_impact": DecisionImpact.BLOCK_PROMOTION.value,
            "resolution": "deferred",
            "resolution_notes": (
                "Defer product-facing claims until horizon-tagged hypothesis families are tested or explicitly scoped."
            ),
            "created_utc": ts,
            "resolution_dependency_review_ids": [rid_lineage],
            "explicit_impact": "requires_horizon_explicit_scope_in_explanation_v2",
            "phase39_batch": True,
        },
    ]


def merge_adversarial_reviews(
    existing: list[dict[str, Any]],
    *,
    lineage_auditor_review_id: str,
) -> list[dict[str, Any]]:
    """Append Phase 39 stances if not already present (idempotent on stance set)."""
    want = {
        ReviewerStance.SKEPTICAL_FUNDAMENTAL.value,
        ReviewerStance.SKEPTICAL_QUANT.value,
        ReviewerStance.REGIME_HORIZON_REVIEWER.value,
    }
    have = {
        str(r.get("reviewer_stance") or "")
        for r in existing
        if str(r.get("hypothesis_id") or "") == PRIMARY_HYPOTHESIS_ID
    }
    if want <= have:
        return existing
    extra = phase39_additional_reviews(lineage_auditor_review_id=lineage_auditor_review_id)
    return list(existing) + extra
