# Phase 31 — Raw-facts bridge after filing-index repair

_Generated (UTC): `2026-04-08T19:11:37.254599+00:00`_

## 핵심 지표 (Before → After)

| 지표 | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_validation_symbol_count | `191` | `161` |
| missing_quarter_snapshot_for_cik | `189` | `158` |
| factor_panel_missing_for_resolved_cik | `189` | `158` |

## 분기 스냅샷 분류 (Before → After)

- `empty_cik`: `1` → `0`
- `filing_index_present_no_raw_facts`: `40` → `0`
- `no_filing_index_for_cik`: `147` → `147`
- `raw_present_no_silver_facts`: `1` → `1`
- `silver_present_snapshot_materialization_missing`: `0` → `10`

## A/B. Raw facts bridge

- repaired_to_raw_present_count: `30`
- deferred_external_source_gap_count: `10`
- blocked_mapping_or_schema_seam_count: `0`
- facts_extract_attempts: `40`

## C. GIS-like silver seam

- actions: `1`

## F. Deterministic issuer (empty_cik / NWSA-class)

- applied: `1`
- blocked: `0`

## D. Downstream retry (raw/issuer touched CIKs)

- cik_count: `30`

## Phase 32 recommendation

- **`continue_silver_snapshot_factor_cascade`**
- rationale: raw_xbrl 다리 후 스냅샷/팩터/검증 델타 — 좁은 연쇄 반복.

