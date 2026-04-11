"""PIT runner family contract — shared schema, per-family spec bindings, shared leakage audit."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = 2
FIXTURE_CLASS = "join_key_mismatch_8"

STANDARD_OUTCOME_BUCKETS = (
    "still_join_key_mismatch",
    "reclassified_to_joined",
    "reclassified_to_other_exclusion",
    "invalid_due_to_leakage_or_non_pit",
)

SHARED_ROW_SCHEMA: dict[str, Any] = {
    "fixture_row_fields": [
        "symbol",
        "cik",
        "signal_available_date",
        "fixture_residual_join_bucket",
    ],
    "per_spec_columns": "dynamic per family (see phase40.family_execution row spec_results keys)",
    "per_spec_cell": {
        "outcome_category": "str",
        "pick_reason": "str",
        "detail": "object",
        "state_change_run_id": "str",
        "optional": ["effective_signal_bound", "lag_calendar_days"],
    },
    "rollup_standard_keys": list(STANDARD_OUTCOME_BUCKETS),
}


def build_pit_runner_family_contract(*, phase38_bundle_path: str) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "fixture_class": FIXTURE_CLASS,
        "phase38_evidence_ref": phase38_bundle_path,
        "shared_row_result_schema": SHARED_ROW_SCHEMA,
        "leakage_audit": {
            "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
            "reused_across_families": True,
            "shared_with_phase38_runner": True,
        },
        "family_bindings": [
            {
                "family_id": "pit_as_of_boundary_v1",
                "hypothesis_ids": ["hyp_pit_join_key_mismatch_as_of_boundary_v1"],
                "alternate_spec_keys_implemented": [
                    "baseline_production_equivalent",
                    "alternate_prior_completed_run",
                    "lag_calendar_signal_bound",
                ],
                "implementation_status": "implemented_phase38",
                "runner_entrypoint": "phase38.pit_runner.run_db_bound_pit_for_join_mismatch_fixture",
            },
            {
                "family_id": "score_publication_cadence_v1",
                "hypothesis_ids": ["hyp_score_publication_cadence_run_grid_lag_v1"],
                "alternate_spec_keys_implemented": ["run_completion_anchored_signal_bound"],
                "planned_spec_keys": ["min_as_of_minus_signal_histogram_spec"],
                "implementation_status": "implemented_phase40",
                "runner_entrypoint": "phase40.family_execution.run_phase40_pit_families",
            },
            {
                "family_id": "signal_filing_boundary_v1",
                "hypothesis_ids": ["hyp_signal_availability_filing_boundary_v1"],
                "alternate_spec_keys_implemented": ["filing_public_ts_strict_pick"],
                "planned_spec_keys": [],
                "implementation_status": "implemented_phase40",
                "runner_entrypoint": "phase40.family_execution.run_phase40_pit_families",
            },
            {
                "family_id": "issuer_sector_cadence_v1",
                "hypothesis_ids": ["hyp_issuer_sector_reporting_cadence_v1"],
                "alternate_spec_keys_implemented": ["stratified_fixture_only_replay"],
                "planned_spec_keys": [],
                "implementation_status": "implemented_phase40",
                "runner_entrypoint": "phase40.family_execution.run_phase40_pit_families",
            },
            {
                "family_id": "governance_join_policy_v1",
                "hypothesis_ids": ["hyp_governance_safe_alternate_join_policy_v1"],
                "alternate_spec_keys_implemented": ["governance_registry_bound_pick"],
                "planned_spec_keys": [],
                "implementation_status": "implemented_phase40",
                "runner_entrypoint": "phase40.family_execution.run_phase40_pit_families",
            },
        ],
        "row_level_comparison": {
            "shared_rollup": "summary_counts_standard",
            "cross_family_compare": "same fixture rows, same four buckets per spec column",
        },
    }
