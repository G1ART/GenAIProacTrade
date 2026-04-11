# Phase 40 — Family PIT spec bindings + shared leakage audit

_Generated (UTC): `2026-04-11T00:36:57.585642+00:00`_
_Bundle generated (UTC): `2026-04-11T00:36:57.584807+00:00`_

## Execution summary

- ok: `True`
- universe: `sp500_current`
- experiment_id: `ec35a18c-1f03-4580-a371-021619d71d96`
- families_executed_count: **5**
- implemented_family_spec_count: **7**
- all_families_leakage_passed: `True`

## Family-level outcomes

- `[{'family_id': 'pit_as_of_boundary_v1', 'hypothesis_id': 'hyp_pit_join_key_mismatch_as_of_boundary_v1', 'spec_keys': ['baseline_production_equivalent', 'alternate_prior_completed_run', 'lag_calendar_signal_bound'], 'leakage_passed': True, 'joined_any_row': False, 'summary_counts_by_spec': {'baseline_production_equivalent': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'alternate_prior_completed_run': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'lag_calendar_signal_bound': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}}, {'family_id': 'score_publication_cadence_v1', 'hypothesis_id': 'hyp_score_publication_cadence_run_grid_lag_v1', 'spec_keys': ['run_completion_anchored_signal_bound'], 'leakage_passed': True, 'joined_any_row': False, 'summary_counts_by_spec': {'run_completion_anchored_signal_bound': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}}, {'family_id': 'signal_filing_boundary_v1', 'hypothesis_id': 'hyp_signal_availability_filing_boundary_v1', 'spec_keys': ['filing_public_ts_strict_pick'], 'leakage_passed': True, 'joined_any_row': False, 'summary_counts_by_spec': {'filing_public_ts_strict_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}}, {'family_id': 'governance_join_policy_v1', 'hypothesis_id': 'hyp_governance_safe_alternate_join_policy_v1', 'spec_keys': ['governance_registry_bound_pick'], 'leakage_passed': True, 'joined_any_row': False, 'summary_counts_by_spec': {'governance_registry_bound_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}}, {'family_id': 'issuer_sector_reporting_cadence_v1', 'hypothesis_id': 'hyp_issuer_sector_reporting_cadence_v1', 'spec_keys': ['stratified_fixture_only_replay'], 'leakage_passed': True, 'joined_any_row': False, 'summary_counts_by_spec': {'stratified_fixture_only_replay': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}}]`

## Leakage audit by family

- `{'pit_as_of_boundary_v1': True, 'score_publication_cadence_v1': True, 'signal_filing_boundary_v1': True, 'governance_join_policy_v1': True, 'issuer_sector_reporting_cadence_v1': True}`

## Lifecycle distribution (after)

- `{'challenged': 1, 'conditionally_supported': 4}`

## Adversarial reviews (Phase 40 family tags)

- `{'score_publication_cadence_v1': 1, 'signal_filing_boundary_v1': 1, 'governance_join_policy_v1': 1, 'issuer_sector_reporting_cadence_v1': 1}`

## Promotion gate

- gate_status: `deferred`
- primary_block_category: `conditionally_supported_but_not_promotable`
- phase40_context: `{'families_executed_count': 5, 'implemented_family_spec_count': 7, 'all_families_leakage_passed': True, 'any_family_joined_row': False, 'conditionally_supported_hypothesis_count': 4}`

## Explanation v3

- `docs/operator_closeout/phase40_explanation_surface_v3.md`

## Phase 41 recommendation

- **`wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4`**
- Phase 40 executed all bounded family specs; several hypotheses remain limited by proxies (filing ts, sector stratification). Next progress is substrate for falsifiers, not more generic PIT keys alone.

## Persistent writes

- `adversarial_reviews_v1` → `data/research_engine/adversarial_reviews_v1.json`
- `hypotheses_v1` → `data/research_engine/hypotheses_v1.json`
- `promotion_gate_history_v1` → `data/research_engine/promotion_gate_history_v1.json`
- `promotion_gate_v1` → `data/research_engine/promotion_gate_v1.json`
