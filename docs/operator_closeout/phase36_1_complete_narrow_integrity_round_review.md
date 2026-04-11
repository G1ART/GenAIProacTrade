# Phase 36.1 — Complete narrow integrity round + public-core freeze line

_Generated (UTC): `2026-04-10T06:50:18.520557+00:00`_

## Closeout summary

- joined_recipe_substrate_row_count: `266`
- joined_market_metadata_flagged_count: `0`
- no_state_change_join: `8`
- metadata_flags_cleared_now_count: `23`
- metadata_flags_still_present_count: `0`
- validation_rebuild_target_count_after_hydration: `23`
- residual_pit_deferred_row_count: `8`
- substrate_freeze_recommendation: `freeze_public_core_and_shift_to_research_engine`
- phase37_recommendation: `execute_research_engine_backlog_sprint`

## Metadata reconciliation (two-pass)

- bucket counts before: `{'stale_metadata_flag_after_join': 23}`
- bucket counts mid (after hydration): `{'stale_metadata_flag_after_join': 23}`
- bucket counts after (after validation rebuild): `{'other_join_metadata_seam': 23}`
- validation_rebuild_factor_panels_submitted: `23`

## Residual no_state_change_join — PIT lab deferral

- policy: `no_broad_state_change_rerun`
- deferred_row_count: `8`
- bucket_counts: `{'state_change_built_but_join_key_mismatch': 8}`
- symbols_deferred: `['ADSK', 'BBY', 'CRM', 'CRWD', 'DELL', 'DUK', 'NVDA', 'WMT']`

## Substrate freeze (re-evaluated)

- `freeze_public_core_and_shift_to_research_engine`
- headline_joined_stable_registry_tail_treated_as_low_roi_deferred; residual_no_sc_rows_8_non_repairable_buckets_only_defer_pit_lab; shift_primary_build_energy_to_research_engine_and_user_facing_layer

## Phase 37

- `execute_research_engine_backlog_sprint`
- Public-core substrate sufficient for MVP freeze; primary energy to hypothesis forge, PIT lab, promotion gate, casebook, explanation layer.
