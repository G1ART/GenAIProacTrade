"""Phase 40 contract manifest — documents implemented family specs (for bundle)."""

from __future__ import annotations

from typing import Any

from phase40.pit_engine import STANDARD_BUCKETS


def build_phase40_contract_manifest(*, phase38_bundle_ref: str) -> dict[str, Any]:
    return {
        "contract_version": 2,
        "fixture_class": "join_key_mismatch_8",
        "phase38_bundle_ref": phase38_bundle_ref,
        "dynamic_row_schema": {
            "spec_results": "dict[str, outcome_cell]",
            "standard_outcome_buckets": list(STANDARD_BUCKETS),
        },
        "leakage_audit_rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
        "families": [
            {
                "family_id": "pit_as_of_boundary_v1",
                "hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1",
                "implemented_spec_keys": [
                    "baseline_production_equivalent",
                    "alternate_prior_completed_run",
                    "lag_calendar_signal_bound",
                ],
            },
            {
                "family_id": "score_publication_cadence_v1",
                "hypothesis_id": "hyp_score_publication_cadence_run_grid_lag_v1",
                "implemented_spec_keys": ["run_completion_anchored_signal_bound"],
            },
            {
                "family_id": "signal_filing_boundary_v1",
                "hypothesis_id": "hyp_signal_availability_filing_boundary_v1",
                "implemented_spec_keys": ["filing_public_ts_strict_pick"],
            },
            {
                "family_id": "governance_join_policy_v1",
                "hypothesis_id": "hyp_governance_safe_alternate_join_policy_v1",
                "implemented_spec_keys": ["governance_registry_bound_pick"],
            },
            {
                "family_id": "issuer_sector_reporting_cadence_v1",
                "hypothesis_id": "hyp_issuer_sector_reporting_cadence_v1",
                "implemented_spec_keys": ["stratified_fixture_only_replay"],
            },
        ],
    }
