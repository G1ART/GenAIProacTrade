"""Additional structured hypotheses for the 8-row join_key_mismatch fixture (no auto-promotion)."""

from __future__ import annotations

from typing import Any

from phase37.hypothesis_registry import HypothesisHorizon, HypothesisStatus

_FIXTURE = ["ADSK", "BBY", "CRM", "CRWD", "DELL", "DUK", "NVDA", "WMT"]
_SCOPE: dict[str, Any] = {
    "universe": "sp500_current",
    "residual_bucket": "state_change_built_but_join_key_mismatch",
    "fixture_symbols": _FIXTURE,
    "fixture_class": "join_key_mismatch_8",
}


def seed_hypothesis_score_publication_cadence() -> dict[str, Any]:
    return {
        "hypothesis_id": "hyp_score_publication_cadence_run_grid_lag_v1",
        "title": (
            "State-change score publication lags create systematic join_key_mismatch vs signal_available_date"
        ),
        "economic_thesis": (
            "Issuer economics may be knowable on the signal calendar, but the score run as_of grid reflects "
            "a coarser publication or batch cadence; mismatch is timing of score availability, not thesis failure."
        ),
        "expected_mechanism": (
            "Comparing signal dates to the earliest as_of in each run and to run completion timestamps "
            "will show systematic grid lag; PIT specs that shift only within the same grid will not unlock rows."
        ),
        "applicable_horizon": HypothesisHorizon.H1Y.value,
        "dependent_features": [
            "state_change_runs.completed_at",
            "state_change_scores.as_of",
            "signal_available_date",
        ],
        "dependent_metrics": [
            "residual_join_bucket_counts.state_change_built_but_join_key_mismatch",
            "run_grid_min_as_of_vs_signal_delta_days",
        ],
        "required_substrate_scope": {**_SCOPE, "needs_run_metadata": True},
        "falsifiers": [
            "Run-grid lag is not systematic across the 8-row fixture (per-issuer noise only).",
            "Unlocking joins requires substrate repair rather than cadence-aware PIT binding.",
        ],
        "status": HypothesisStatus.DRAFT.value,
        "lifecycle_transitions": [],
    }


def seed_hypothesis_signal_filing_boundary() -> dict[str, Any]:
    return {
        "hypothesis_id": "hyp_signal_availability_filing_boundary_v1",
        "title": "signal_available_date semantics omit filing or public-availability boundaries relevant to PIT",
        "economic_thesis": (
            "The pipeline signal_available_date may align to an internal recipe date while filers public "
            "availability differs; strict bisect_right against score as_of then correctly excludes under production rules."
        ),
        "expected_mechanism": (
            "Cross-checking EDGAR filing timestamps vs signal_available_date will show whether "
            "the residual is a definitional boundary, not missing SC rows."
        ),
        "applicable_horizon": HypothesisHorizon.H1Y.value,
        "dependent_features": [
            "signal_available_date",
            "filing_publication_timeline",
            "state_change_scores.as_of",
        ],
        "dependent_metrics": [
            "signal_minus_filing_availability_days",
            "residual_join_bucket_counts.state_change_built_but_join_key_mismatch",
        ],
        "required_substrate_scope": {**_SCOPE, "needs_filing_timeline_sample": True},
        "falsifiers": [
            "Signal dates are already conservative vs any defensible public-availability bound for all 8 rows.",
            "Adjusting only filing semantics does not change join classification under audited PIT.",
        ],
        "status": HypothesisStatus.DRAFT.value,
        "lifecycle_transitions": [],
    }


def seed_hypothesis_issuer_sector_cadence() -> dict[str, Any]:
    return {
        "hypothesis_id": "hyp_issuer_sector_reporting_cadence_v1",
        "title": "Issuer or sector reporting cadence interacts with quarterly score grids",
        "economic_thesis": (
            "Certain sectors cluster fiscal period ends and restatement windows; the eight symbols may share "
            "patterns where score as-of grids systematically trail economically relevant signal timing."
        ),
        "expected_mechanism": (
            "Sector stratified analysis of signal vs min-as_of deltas across the fixture and broader universe "
            "will show clustering; absence of clustering falsifies sector-driven mechanism."
        ),
        "applicable_horizon": HypothesisHorizon.H3_5Y.value,
        "dependent_features": [
            "gics_sector",
            "fiscal_year_end_proxy",
            "state_change_scores.as_of",
            "signal_available_date",
        ],
        "dependent_metrics": [
            "fixture_sector_distribution",
            "delta_days_signal_to_min_as_of_by_sector",
        ],
        "required_substrate_scope": {**_SCOPE, "stratification": "sector"},
        "falsifiers": [
            "Fixture shows no sector clustering beyond chance for signal to min-as_of gaps.",
            "Within-sector controls still show join_key_mismatch only from non-cadence causes.",
        ],
        "status": HypothesisStatus.DRAFT.value,
        "lifecycle_transitions": [],
    }


def seed_hypothesis_governance_safe_join_policy() -> dict[str, Any]:
    return {
        "hypothesis_id": "hyp_governance_safe_alternate_join_policy_v1",
        "title": (
            "Governance-approved alternate join policies could reclassify some rows without leakage"
        ),
        "economic_thesis": (
            "Production uses one pick rule; research may define additional rules that remain PIT-safe and "
            "documented; some mismatches are policy choice, not data error."
        ),
        "expected_mechanism": (
            "Under explicit governance, alternate spec keys map to testable PIT bindings in the family contract; "
            "leakage audit remains shared."
        ),
        "applicable_horizon": HypothesisHorizon.H1Y.value,
        "dependent_features": [
            "pick_state_change_at_or_before_signal",
            "governance_join_policy_registry",
        ],
        "dependent_metrics": [
            "reclassified_to_joined_under_governed_alternate_spec",
            "invalid_due_to_leakage_or_non_pit",
        ],
        "required_substrate_scope": {**_SCOPE, "needs_governance_signoff": True},
        "falsifiers": [
            "No governance-safe alternate policy yields joined outcomes for the fixture without leakage violations.",
            "Any unlocking policy collapses to lookahead under the shared audit rule.",
        ],
        "status": HypothesisStatus.DRAFT.value,
        "lifecycle_transitions": [],
    }


def all_phase39_hypothesis_seeds() -> list[dict[str, Any]]:
    return [
        seed_hypothesis_score_publication_cadence(),
        seed_hypothesis_signal_filing_boundary(),
        seed_hypothesis_issuer_sector_cadence(),
        seed_hypothesis_governance_safe_join_policy(),
    ]
