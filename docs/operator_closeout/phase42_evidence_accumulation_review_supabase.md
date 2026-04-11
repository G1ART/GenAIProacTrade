# Phase 42 — Evidence accumulation

_Generated (UTC): `2026-04-11T05:54:42.805109+00:00`_
_Bundle generated (UTC): `2026-04-11T05:54:33.329066+00:00`_

## Execution summary

- ok: `True`
- phase41_bundle: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase41_falsifier_substrate_bundle.json`
- stable_run_digest: `edfd0b7d36ecb2de`

## Scorecard

- `{'cohort_label': 'phase41_fixture_row_results', 'cohort_row_count': 8, 'filing_blocker_distribution': {'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}, 'sector_blocker_distribution': {'no_market_metadata_row_for_symbol': 8}, 'phase41_families': ['signal_filing_boundary_v1', 'issuer_sector_reporting_cadence_v1'], 'outcome_discriminating_family_count': 2, 'identical_rollup_groups': []}`

## Discrimination

- `{'n_families_compared': 2, 'outcome_rollup_signature_by_family': {'signal_filing_boundary_v1': "(('filing_public_ts_strict_pick', (('invalid_due_to_leakage_or_non_pit', 0), ('reclassified_to_joined', 0), ('reclassified_to_other_exclusion', 0), ('still_join_key_mismatch', 8))),)", 'issuer_sector_reporting_cadence_v1': "(('sector_stratified_signal_pick_v1', (('invalid_due_to_leakage_or_non_pit', 0), ('reclassified_to_joined', 0), ('reclassified_to_other_exclusion', 0), ('still_join_key_mismatch', 8))),)"}, 'families_with_identical_rollups_groups': [], 'live_and_discriminating_family_ids': ['signal_filing_boundary_v1', 'issuer_sector_reporting_cadence_v1'], 'any_family_outcome_discriminating': True}`

## Narrowing

- `{'by_family_id': {'signal_filing_boundary_v1': {'hypothesis_id': 'hyp_signal_availability_filing_boundary_v1', 'narrowing_status': 'live_and_discriminating', 'proxy_limited_substrate': True, 'suggested_claim_adjustment': None}, 'issuer_sector_reporting_cadence_v1': {'hypothesis_id': 'hyp_issuer_sector_reporting_cadence_v1', 'narrowing_status': 'live_and_discriminating', 'proxy_limited_substrate': True, 'suggested_claim_adjustment': None}}, 'headline': 'at_least_one_family_outcome_discriminating'}`

## Promotion gate

- gate_status: `deferred`
- primary_block_category: `deferred_due_to_proxy_limited_falsifier_substrate`
- phase42_context: `{'all_families_leakage_passed_phase41': True, 'filing_proxy_row_count': 8, 'sector_missing_row_count': 8, 'any_family_outcome_discriminating': True, 'narrowing_headline': 'at_least_one_family_outcome_discriminating'}`

## Explanation v5

- `docs/operator_closeout/phase42_explanation_surface_v5_supabase.md`

## Phase 43 recommendation

- **`substrate_backfill_or_narrow_claims_then_retest_v1`**
- Proxy filing bounds or missing sector rows remain; strengthen rows (backfill) or narrow claims before expecting cleaner discrimination.
