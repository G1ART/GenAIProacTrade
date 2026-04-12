# Explanation surface v7 — Phase 44 (truthfulness after Phase 43)

## What Phase 43 improved

- **Sector taxonomy precision**: scorecard bucket moved from `no_market_metadata_row_for_symbol` to `sector_field_blank_on_metadata_row` for the 8-row cohort, matching runtime rows where metadata exists but `sector` is empty.
- **Stable digest** changed between Phase 42 runs bracketing Phase 43 (see Phase 43 bundle); this records execution drift, not by itself a falsifier upgrade.

## What Phase 43 did not improve

- **Filing falsifier strength** (aggregate): `exact_public_ts_available` and related usability counts did not increase; filing blocker distribution is unchanged at the scorecard level.
- **Sector usability**: `sector_available` did not increase; sector-informed falsification remains unavailable.
- **Gate**: `gate_status` and `primary_block_category` unchanged (still proxy-limited substrate).
- **Discrimination rollups**: family outcome signatures unchanged for this cohort.

## Is another bounded retry justified?

- Phase 44 material improvement flag: **False**.
- Filing retry eligible: **False**; sector retry eligible: **False**.
- Without a **newly named** source/path, generic “run another bounded pass” is **not** authorized.

## Narrowed claims (machine-readable summary)

- Cohort status: `narrowed`
- Bounded retry registry: `not_eligible_without_named_new_path`

### Scorecard anchors

- Phase 42 Supabase (before Phase 43): `{'no_market_metadata_row_for_symbol': 8}` / `{'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}`
- After Phase 43 Phase 42 rerun: `{'sector_field_blank_on_metadata_row': 8}` / `{'no_10k_10q_rows_for_cik': 7, 'only_post_signal_filings_available': 1}`

## Broad substrate reopening

Broad public-core filing_index or metadata campaigns remain **out of scope**; Phase 44 is a governance and interpretation patch, not a substrate expansion.

## Phase 45 recommendation

- **`narrow_claims_document_proxy_limits_operator_closeout_v1`** — No material falsifier upgrade under Phase 44 rules; do not reopen broad substrate. Narrow claims, document proxy limits, and close out unless new evidence appears.
