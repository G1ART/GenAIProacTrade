# Research explanation (Phase 41 v4)

_Supports human judgment only. **Not** investment advice; no buy/sell/hold recommendation._

## What substrate was wired

- **Filing**: `filing_index` rows per fixture CIK; per-row classification `exact_filing_public_ts_available` | `exact_filing_filed_date_available` | `filing_public_ts_unavailable` (explicit `signal_available_date` proxy when unavailable).
- **Sector**: `market_metadata_latest.sector` (deterministic pick per symbol); `sector_metadata_available` | `sector_metadata_missing` (stratum `unknown`).

## Filing substrate summary

- `{'row_count': 8, 'by_classification': {'filing_public_ts_unavailable': 8}, 'rows_with_explicit_signal_proxy': 8}`

## Sector substrate summary

- `{'row_count': 8, 'by_classification': {'sector_metadata_missing': 8}, 'distinct_sector_labels': []}`

## Families re-executed (Phase 41)

### `signal_filing_boundary_v1`
- **Specs**: ['filing_public_ts_strict_pick']
- **Leakage passed**: `True`
- **Rollups**: `{'filing_public_ts_strict_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

### `issuer_sector_reporting_cadence_v1`
- **Specs**: ['sector_stratified_signal_pick_v1']
- **Leakage passed**: `True`
- **Rollups**: `{'sector_stratified_signal_pick_v1': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`
- **By sector stratum**: `{'unknown': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

## Before vs after (vs Phase 40 bundle, if provided)

- `{'signal_filing_boundary_v1': {'before_summary_counts_by_spec': {'filing_public_ts_strict_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}, 'after_summary_counts_by_spec': {'filing_public_ts_strict_pick': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}, 'spec_keys_before': ['filing_public_ts_strict_pick'], 'spec_keys_after': ['filing_public_ts_strict_pick'], 'unchanged_rollups': True}, 'issuer_sector_reporting_cadence_v1': {'before_summary_counts_by_spec': {'stratified_fixture_only_replay': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}, 'after_summary_counts_by_spec': {'sector_stratified_signal_pick_v1': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}, 'spec_keys_before': ['stratified_fixture_only_replay'], 'spec_keys_after': ['sector_stratified_signal_pick_v1'], 'unchanged_rollups': False}}`

## What changed vs stayed the same

- Outcome **counts** may match Phase 40 when bounds coincide; v4 value is **explicit** filing/sector labels and pick metadata on each cell.
- Rows still on **signal proxy** for filing or **unknown** sector stratum are labeled—not silent.

## Promotion gate (v4)

- **gate_status**: `deferred`
- **primary_block_category**: `deferred_due_to_proxy_limited_falsifier_substrate`
- **phase41_context**: `{'filing_proxy_row_count': 8, 'filing_row_count': 8, 'sector_missing_row_count': 8, 'sector_row_count': 8, 'all_families_leakage_passed': True}`

## Phase 42 (recommended next)

- **`accumulate_evidence_and_narrow_hypotheses_under_stronger_falsifiers_v1`**
- Phase 41 wired filing_index and sector metadata for targeted families; next work is evidence accumulation, competing-hypothesis discrimination, or explanation/governance tightening—not broad substrate repair.
