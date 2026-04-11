# Research explanation (Phase 43 v6 — bounded falsifier substrate backfill)

_Judgment support only. Not investment advice; no buy/sell/hold._

## What ran

- **Cohort**: exactly 8 rows from Phase 42 Supabase-fresh `row_level_blockers` (no universe expansion).
- **Filing**: bounded `run_sample_ingest` per distinct CIK (capped).
- **Sector**: `run_market_metadata_hydration_for_symbols` for those 8 symbols only.
- **Retest**: Phase 41 two families again, then Phase 42 with **Supabase-fresh** blockers (authoritative).

## Backfill actions (summary)

- **filing**: `{'repair': 'bounded_run_sample_ingest_per_cik', 'max_cik_repairs': 8, 'unique_ciks_touched': 8, 'attempts': [{'cik': '0000764478', 'symbol': 'BBY', 'ticker': 'BBY', 'status': 'attempted', 'ingest_summary': {'ticker': 'BBY', 'cik': '0000764478', 'accession_no': '0000102909-26-000776', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0000769397', 'symbol': 'ADSK', 'ticker': 'ADSK', 'status': 'attempted', 'ingest_summary': {'ticker': 'ADSK', 'cik': '0000769397', 'accession_no': '0000769397-26-000017', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0001108524', 'symbol': 'CRM', 'ticker': 'CRM', 'status': 'attempted', 'ingest_summary': {'ticker': 'CRM', 'cik': '0001108524', 'accession_no': '0001108524-26-000083', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0001535527', 'symbol': 'CRWD', 'ticker': 'CRWD', 'status': 'attempted', 'ingest_summary': {'ticker': 'CRWD', 'cik': '0001535527', 'accession_no': '0001535527-26-000013', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0001571996', 'symbol': 'DELL', 'ticker': 'DELL', 'status': 'attempted', 'ingest_summary': {'ticker': 'DELL', 'cik': '0001571996', 'accession_no': '0001959173-26-002845', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0001326160', 'symbol': 'DUK', 'ticker': 'DUK', 'status': 'attempted', 'ingest_summary': {'ticker': 'DUK', 'cik': '0001326160', 'accession_no': '0001491154-26-000002', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0001045810', 'symbol': 'NVDA', 'ticker': 'NVDA', 'status': 'attempted', 'ingest_summary': {'ticker': 'NVDA', 'cik': '0001045810', 'accession_no': '0000102909-26-000426', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}, {'cik': '0000104169', 'symbol': 'WMT', 'ticker': 'WMT', 'status': 'attempted', 'ingest_summary': {'ticker': 'WMT', 'cik': '0000104169', 'accession_no': '0002110643-26-000008', 'issuer_upserted': True, 'filing_index_inserted': False, 'filing_index_updated': True, 'raw_inserted': False, 'silver_inserted': False}}]}`
- **sector**: `{'status': 'completed', 'symbols_requested': 8, 'provider_rows_returned': 8, 'rows_attempted_for_upsert': 8, 'rows_already_current': 8, 'rows_upserted': 0, 'rows_missing_after_requery': 0, 'provider': 'yahoo_chart'}`

## Scorecard (Phase 42 family evidence)

- **before**: `{'cohort_label': 'phase41_fixture_row_results', 'cohort_row_count': 8, 'filing_blocker_distribution': {'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}, 'sector_blocker_distribution': {'no_market_metadata_row_for_symbol': 8}, 'phase41_families': ['signal_filing_boundary_v1', 'issuer_sector_reporting_cadence_v1'], 'outcome_discriminating_family_count': 2, 'identical_rollup_groups': []}`
- **after**: `{'cohort_label': 'phase41_fixture_row_results', 'cohort_row_count': 8, 'filing_blocker_distribution': {'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}, 'sector_blocker_distribution': {'sector_field_blank_on_metadata_row': 8}, 'phase41_families': ['signal_filing_boundary_v1', 'issuer_sector_reporting_cadence_v1'], 'outcome_discriminating_family_count': 2, 'identical_rollup_groups': []}`
- **stable_run_digest**: `edfd0b7d36ecb2de` → `285b046cc5bcb307`

## Gate (Phase 42 payload)

- **before** `primary_block_category`: `deferred_due_to_proxy_limited_falsifier_substrate`
- **after** `primary_block_category`: `deferred_due_to_proxy_limited_falsifier_substrate`

## Before/after rows (abbrev)

- `8` rows — see `phase43_targeted_substrate_before_after_audit.md` for full tables.

## Phase 41 rerun (after backfill)

- **ok**: `True`
- **experiment_id**: `5ae2780b-5978-4522-b1f5-0ece15844e0f`

## Phase 42 rerun (authoritative)

- **ok**: `True`
- **phase42_used_supabase_fresh**: `True`

## Phase 44 (recommended next)

- **`continue_bounded_falsifier_retest_or_narrow_claims_v1`**
- Bounded backfill or retest changed at least one row-level blocker, scorecard bucket, or gate field. Next: optional second bounded pass, or narrow claims if proxy limits persist.
