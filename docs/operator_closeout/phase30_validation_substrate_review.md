# Phase 30 — Upstream validation substrate (filing / silver / snapshot chain)

_Generated (UTC): `2026-04-08T15:50:40.268208+00:00`_

## 핵심 지표 (Before → After)

| 지표 | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_validation_symbol_count | `191` | `191` |
| missing_quarter_snapshot_for_cik | `189` | `189` |
| factor_panel_missing_for_resolved_cik | `189` | `189` |

## 분기 스냅샷 분류 counts (Before → After)

- `empty_cik`: `1` → `1`
- `filing_index_present_no_raw_facts`: `0` → `40`
- `no_filing_index_for_cik`: `187` → `147`
- `raw_present_no_silver_facts`: `1` → `1`

## A. Filing index gap repair

- preflight_unique_targets: `187`
- repaired_now_count: `40`
- deferred_external_source_gap_count: `147`
- blocked_identity_or_mapping_issue_count: `0`
- network_ingest_attempts: `40`

## B. Silver facts materialization (`raw_present_no_silver_facts`)

- cik_repairs_attempted: `1`
- actions rows: `1`

## C. Empty CIK / normalization

- note: `classification_only_no_automatic_mutations_in_v1`
- diagnoses: `1`

## D. Downstream cascade (touched CIKs only)

- cik_count: `40`

## Phase 31 recommendation

- **`continue_bounded_sec_substrate_ingest`**
- rationale: no_filing_index_for_cik 감소 — 동일 상한·감사로 SEC substrate ingest 반복.

