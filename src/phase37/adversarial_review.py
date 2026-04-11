"""Structured adversarial peer review — queryable records, not chat dumps."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ReviewerStance(str, Enum):
    SKEPTIC_FUNDAMENTAL = "skeptic_fundamental"
    SKEPTIC_QUANT = "skeptic_quant"
    RISK_OFF_REGULATOR = "risk_off_regulator"
    DATA_LINEAGE_AUDITOR = "data_lineage_auditor"
    # Phase 39+ explicit labels (workorder naming)
    SKEPTICAL_FUNDAMENTAL = "skeptical_fundamental"
    SKEPTICAL_QUANT = "skeptical_quant"
    REGIME_HORIZON_REVIEWER = "regime_horizon_reviewer"


class CritiqueCategory(str, Enum):
    THESIS = "thesis"
    MECHANISM = "mechanism"
    DATA = "data"
    PIT_INTEGRITY = "pit_integrity"
    HORIZON_MISMATCH = "horizon_mismatch"


class ChallengeResolution(str, Enum):
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    FATAL = "fatal"


class DecisionImpact(str, Enum):
    NONE = "none"
    BLOCK_PROMOTION = "block_promotion"
    REQUIRE_EXTRA_TEST = "require_extra_test"
    DOWNGRADE_CONFIDENCE = "downgrade_confidence"


@dataclass
class AdversarialReviewRecordV1:
    review_id: str
    hypothesis_id: str
    reviewer_stance: str
    critique_category: str
    challenge_text: str
    decision_impact: str
    resolution: str
    resolution_notes: str
    created_utc: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def seed_adversarial_review_for_pit_hypothesis() -> AdversarialReviewRecordV1:
    return AdversarialReviewRecordV1(
        review_id=str(uuid4()),
        hypothesis_id="hyp_pit_join_key_mismatch_as_of_boundary_v1",
        reviewer_stance=ReviewerStance.DATA_LINEAGE_AUDITOR.value,
        critique_category=CritiqueCategory.PIT_INTEGRITY.value,
        challenge_text=(
            "Alternate state_change run selection might smuggle lookahead if the run's as_of grid "
            "is not strictly ≤ signal_available_date under the same governance rules as production."
        ),
        decision_impact=DecisionImpact.REQUIRE_EXTRA_TEST.value,
        resolution=ChallengeResolution.DEFERRED.value,
        resolution_notes=(
            "Deferred until Phase 38 DB-bound PIT runner proves deterministic boundaries for each "
            "alternate spec; no promotion until documented."
        ),
        created_utc=datetime.now(timezone.utc).isoformat(),
    )


def default_adversarial_reviews() -> list[dict[str, Any]]:
    return [seed_adversarial_review_for_pit_hypothesis().to_json_dict()]
