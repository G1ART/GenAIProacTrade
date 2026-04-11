"""Hypothesis registry v1 — structured objects, no auto-promotion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class HypothesisHorizon(str, Enum):
    H1Y = "1y"
    H3_5Y = "3-5y"
    H5_10Y = "5-10y"


class HypothesisStatus(str, Enum):
    DRAFT = "draft"
    UNDER_TEST = "under_test"
    CHALLENGED = "challenged"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CONDITIONALLY_SUPPORTED = "conditionally_supported"


@dataclass
class HypothesisV1:
    hypothesis_id: str
    title: str
    economic_thesis: str
    expected_mechanism: str
    applicable_horizon: str
    dependent_features: list[str] = field(default_factory=list)
    dependent_metrics: list[str] = field(default_factory=list)
    required_substrate_scope: dict[str, Any] = field(default_factory=dict)
    falsifiers: list[str] = field(default_factory=list)
    status: str = HypothesisStatus.DRAFT.value
    lifecycle_transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def seed_hypothesis_join_key_mismatch_pit() -> HypothesisV1:
    """First executable hypothesis: PIT boundary for residual no_state_change_join rows."""
    return HypothesisV1(
        hypothesis_id="hyp_pit_join_key_mismatch_as_of_boundary_v1",
        title="Residual no_state_change_join (join_key_mismatch) reflects score-run as-of vs signal-date ordering, not missing SC build",
        economic_thesis=(
            "For a subset of joined recipe rows, state_change scores exist but the earliest as_of in the "
            "referenced run is after the signal_available_date; joins fail under current PIT keys while "
            "economic content may still be coherent under alternate as-of or lag conventions."
        ),
        expected_mechanism=(
            "Replaying join logic under alternate state_change run selection or explicit lag windows "
            "will reclassify some rows from join_key_mismatch to joined or to a documented exclusion bucket."
        ),
        applicable_horizon=HypothesisHorizon.H1Y.value,
        dependent_features=[
            "state_change_scores.as_of",
            "signal_available_date",
            "pick_state_change_at_or_before_signal",
            "joined_recipe_substrate_row",
        ],
        dependent_metrics=[
            "no_state_change_join_headline",
            "residual_join_bucket_counts.state_change_built_but_join_key_mismatch",
        ],
        required_substrate_scope={
            "universe": "sp500_current",
            "residual_bucket": "state_change_built_but_join_key_mismatch",
            "fixture_symbols": [
                "ADSK",
                "BBY",
                "CRM",
                "CRWD",
                "DELL",
                "DUK",
                "NVDA",
                "WMT",
            ],
        },
        falsifiers=[
            "All eight rows remain join_key_mismatch under every deterministic alternate run spec in the PIT harness.",
            "Alternate boundaries introduce lookahead or non-PIT leakage per audit rules.",
        ],
        status=HypothesisStatus.UNDER_TEST.value,
        lifecycle_transitions=[],
    )


def default_hypothesis_registry() -> list[dict[str, Any]]:
    return [seed_hypothesis_join_key_mismatch_pit().to_json_dict()]
