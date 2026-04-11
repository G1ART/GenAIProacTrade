# Research explanation (Phase 40 v3)

_This document supports human judgment. It is **not** a buy, sell, or hold recommendation and does not constitute investment advice._

## What ran (families)

### `pit_as_of_boundary_v1`
- **Specs**: ['baseline_production_equivalent', 'alternate_prior_completed_run', 'lag_calendar_signal_bound']
- **Leakage audit passed**: `True`
- **Any row joined under this family**: `False`
- **Rollups by spec**: `{'baseline_production_equivalent': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'alternate_prior_completed_run': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'lag_calendar_signal_bound': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

### `score_publication_cadence_v1`
- **Specs**: ['run_completion_anchored_signal_bound']
- **Leakage audit passed**: `True`
- **Any row joined under this family**: `False`
- **Rollups by spec**: `{'run_completion_anchored_signal_bound': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

### `signal_filing_boundary_v1`
- **Specs**: ['filing_public_ts_strict_pick']
- **Leakage audit passed**: `True`
- **Any row joined under this family**: `False`
- **Rollups by spec**: `{'filing_public_ts_strict_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

### `governance_join_policy_v1`
- **Specs**: ['governance_registry_bound_pick']
- **Leakage audit passed**: `True`
- **Any row joined under this family**: `False`
- **Rollups by spec**: `{'governance_registry_bound_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

### `issuer_sector_reporting_cadence_v1`
- **Specs**: ['stratified_fixture_only_replay']
- **Leakage audit passed**: `True`
- **Any row joined under this family**: `False`
- **Rollups by spec**: `{'stratified_fixture_only_replay': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

## Which families changed outcomes vs Phase 38 baseline?

Compare `summary_counts_by_spec` to the `pit_as_of_boundary_v1` family (legacy trio). For this fixture, many single-spec replays intentionally mirror baseline or use bounded signal caps; **no automatic claim of economic resolution**.

## Untested or proxy-limited

- **Filing boundary** family uses `signal_available_date` as a **documented proxy** when EDGAR public timestamps are absent.
- **Sector cadence** family currently replays the **same pick rule** on the fixture cohort only; it does not yet stratify by GICS.

## Lifecycle snapshot (after Phase 40)

- `{'hyp_pit_join_key_mismatch_as_of_boundary_v1': 'challenged', 'hyp_score_publication_cadence_run_grid_lag_v1': 'conditionally_supported', 'hyp_signal_availability_filing_boundary_v1': 'conditionally_supported', 'hyp_issuer_sector_reporting_cadence_v1': 'conditionally_supported', 'hyp_governance_safe_alternate_join_policy_v1': 'conditionally_supported'}`

## Promotion gate

- **gate_status**: `deferred`
- **primary_block_category**: `conditionally_supported_but_not_promotable`
- **phase40_context**: `{'families_executed_count': 5, 'implemented_family_spec_count': 7, 'all_families_leakage_passed': True, 'any_family_joined_row': False, 'conditionally_supported_hypothesis_count': 4}`

## Phase 41 (recommended next)

- **`wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4`**
- Phase 40 executed all bounded family specs; several hypotheses remain limited by proxies (filing ts, sector stratification). Next progress is substrate for falsifiers, not more generic PIT keys alone.
