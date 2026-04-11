# Phase 34 — Forward→validation propagation + maturity-aware retry

_Generated (UTC): `2026-04-09T00:36:33.860962+00:00`_

## Closeout summary

- joined_recipe_substrate_row_count: `243`
- thin_input_share: `1`
- missing_excess_return_1q: `78`
- missing_validation_symbol_count: `151`
- missing_quarter_snapshot_for_cik: `148`
- factor_panel_missing_for_resolved_cik: `148`
- forward_row_present_count (final gap): `23`
- validation_excess_filled_now_count: `23`
- symbol_cleared_from_missing_excess_queue_count (after refresh truth): `23`
- joined_recipe_unlocked_now_count (headline delta): `0`
- matured_forward_retry_success_count: `0`
- still_not_matured_count: `7`
- price_coverage_repaired_now_count: `0`
- GIS outcome: `blocked_unmapped_concepts_remain_in_sample`
- GIS blocked_reason: `concept_map_misses_for_sampled_raw_concepts`

## Headline substrate (Before → After)

| Metric | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_excess_return_1q | `101` | `78` |
| missing_validation_symbol_count | `151` | `151` |
| missing_quarter_snapshot_for_cik | `148` | `148` |
| factor_panel_missing_for_resolved_cik | `148` | `148` |

## Propagation gap classification (initial → final)

- `forward_not_present_other_gap`: `0` → `0`
- `forward_not_present_window_not_matured`: `7` → `7`
- `forward_present_validation_not_refreshed`: `23` → `0`
- `forward_present_validation_refresh_failed`: `0` → `0`
- `synchronized`: `0` → `23`

## Phase 35 recommendation

- `re_audit_forward_validation_join_and_schedule_matured_windows`
- 기판 또는 터치 집합 전파·forward에 진전 — 동일 상한으로 재감사 및 성숙 창만 후속 재시도.
