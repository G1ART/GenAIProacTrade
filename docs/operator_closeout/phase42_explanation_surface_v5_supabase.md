# Research explanation (Phase 42 v5)

_Human judgment only. **Not** investment advice; no buy/sell/hold recommendation._

## Evidence scorecard (cohort A)

- **cohort_row_count**: `8`
- **filing_blocker_distribution**: `{'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}`
- **sector_blocker_distribution**: `{'no_market_metadata_row_for_symbol': 8}`
- **outcome_discriminating_family_count**: `2`

## Outcome discrimination (Phase 41 family rollups)

- **any_family_outcome_discriminating**: `True`
- **live_and_discriminating_family_ids**: `['signal_filing_boundary_v1', 'issuer_sector_reporting_cadence_v1']`
- **families_with_identical_rollups_groups**: `[]`

## Hypothesis narrowing (labels only)

- **headline**: `at_least_one_family_outcome_discriminating`
- **by_family_id**: `{'signal_filing_boundary_v1': {'hypothesis_id': 'hyp_signal_availability_filing_boundary_v1', 'narrowing_status': 'live_and_discriminating', 'proxy_limited_substrate': True, 'suggested_claim_adjustment': None}, 'issuer_sector_reporting_cadence_v1': {'hypothesis_id': 'hyp_issuer_sector_reporting_cadence_v1', 'narrowing_status': 'live_and_discriminating', 'proxy_limited_substrate': True, 'suggested_claim_adjustment': None}}`

## Promotion gate (v4 context, Phase 42)

- **gate_status**: `deferred`
- **primary_block_category**: `deferred_due_to_proxy_limited_falsifier_substrate`
- **blocking_reasons**: `['filing_proxy_or_blocker_rows_remain', 'sector_metadata_missing_rows_remain', 'await_stronger_falsifier_substrate']`
- **phase42_context**: `{'all_families_leakage_passed_phase41': True, 'filing_proxy_row_count': 8, 'sector_missing_row_count': 8, 'any_family_outcome_discriminating': True, 'narrowing_headline': 'at_least_one_family_outcome_discriminating'}`

## Run digest

- **stable_run_digest**: `edfd0b7d36ecb2de`

## Phase 43 (recommended next)

- **`substrate_backfill_or_narrow_claims_then_retest_v1`**
- Proxy filing bounds or missing sector rows remain; strengthen rows (backfill) or narrow claims before expecting cleaner discrimination.
