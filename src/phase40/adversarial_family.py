"""Family-scoped adversarial reviews (Phase 40) — append-only, idempotent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from phase37.adversarial_review import CritiqueCategory, DecisionImpact, ReviewerStance

BATCH_TAG = "phase40_family_execution_review"


def family_execution_reviews(
    *,
    families_executed: list[dict[str, Any]],
    transitioned_utc: str | None = None,
) -> list[dict[str, Any]]:
    ts = transitioned_utc or datetime.now(timezone.utc).isoformat()
    templates: list[tuple[str, str, str, str, str]] = [
        (
            "hyp_score_publication_cadence_run_grid_lag_v1",
            "Run completion anchoring may still be too coarse if intra-day publication matters; "
            "grid lag hypothesis needs run timestamps vs score as_of alignment across more than one run.",
            CritiqueCategory.DATA.value,
            DecisionImpact.REQUIRE_EXTRA_TEST.value,
            "score_publication_cadence_v1",
        ),
        (
            "hyp_signal_availability_filing_boundary_v1",
            "Filing-public proxy equals signal_available_date until EDGAR timestamps are wired; "
            "do not treat this execution as filing-semantics falsification.",
            CritiqueCategory.DATA.value,
            DecisionImpact.DOWNGRADE_CONFIDENCE.value,
            "signal_filing_boundary_v1",
        ),
        (
            "hyp_governance_safe_alternate_join_policy_v1",
            "Registry lag is research-governed but not product-approved; promotion still requires "
            "explicit policy signoff beyond JSON registry.",
            CritiqueCategory.PIT_INTEGRITY.value,
            DecisionImpact.BLOCK_PROMOTION.value,
            "governance_join_policy_v1",
        ),
        (
            "hyp_issuer_sector_reporting_cadence_v1",
            "Stratified fixture replay currently equals production pick on the same rows; "
            "sector stratification needs universe slice or metadata before it discriminates mechanisms.",
            CritiqueCategory.MECHANISM.value,
            DecisionImpact.REQUIRE_EXTRA_TEST.value,
            "issuer_sector_reporting_cadence_v1",
        ),
    ]
    out: list[dict[str, Any]] = []
    fids = {str(f.get("family_id") or "") for f in families_executed}
    for hid, text, cat, impact, fid in templates:
        if fid not in fids:
            continue
        out.append(
            {
                "review_id": str(uuid4()),
                "hypothesis_id": hid,
                "reviewer_stance": ReviewerStance.DATA_LINEAGE_AUDITOR.value,
                "critique_category": cat,
                "challenge_text": text,
                "decision_impact": impact,
                "resolution": "deferred",
                "resolution_notes": "Phase 40 family execution batch; queryable with family_id.",
                "created_utc": ts,
                BATCH_TAG: True,
                "phase40_family_id": fid,
                "explicit_impact": "family_scoped_governance_record",
            }
        )
    return out


def merge_family_adversarial(existing: list[dict[str, Any]], new_batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    have = {
        (str(r.get("hypothesis_id")), str(r.get("phase40_family_id")))
        for r in existing
        if r.get(BATCH_TAG) and r.get("phase40_family_id")
    }
    extra = []
    for r in new_batch:
        key = (str(r.get("hypothesis_id")), str(r.get("phase40_family_id")))
        if key not in have:
            extra.append(r)
            have.add(key)
    return list(existing) + extra
