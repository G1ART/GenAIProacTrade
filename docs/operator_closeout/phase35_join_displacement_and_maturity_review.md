# Phase 35 — Join displacement + state_change seam + maturity schedule

_Generated (UTC): `2026-04-09T04:53:34.557864+00:00`_

## Closeout summary

- joined_recipe_substrate_row_count: `266`
- joined_market_metadata_flagged_count (after): `23` (before `0`)
- thin_input_share: `1`
- missing_excess_return_1q: `78`
- missing_validation_symbol_count: `151`
- missing_quarter_snapshot_for_cik: `148`
- factor_panel_missing_for_resolved_cik: `148`
- no_state_change_join (after): `8`
- joined_recipe_unlocked_now_count (headline delta): `23`
- no_state_change_join_cleared_count: `23`
- matured_eligible_now_count: `0`
- still_not_matured_count: `7`
- matured_forward_retry_success_count: `0`
- price_coverage_repaired_now_count: `0`
- GIS outcome: `blocked_unmapped_concepts_remain_in_sample`

## Hypothesis (23 synchronized → no_state_change_join)

- **초기** (`forward_validation_join_displacement_initial`): supported_by_counts `True` — included `0`, excluded_no_state_change_join `23`, 이음새 전부 `state_change_not_built_for_row`.
- **최종** (`forward_validation_join_displacement_final`): supported_by_counts `False` — included `23`, excluded_no_state_change_join `0` (refresh 후 전부 joined).

## Headline substrate (Before → After)

| Metric | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `266` |
| joined_market_metadata_flagged_count | `0` | `23` |
| thin_input_share | `1` | `1` |
| missing_excess_return_1q | `78` | `78` |
| no_state_change_join | `31` | `8` |

## Displacement counts on synchronized set (initial → final)

- initial: `{'excluded_no_state_change_join': 23}`
- final: `{'included_in_joined_recipe_substrate': 23}`

## Phase 36 recommendation

- `continue_join_audit_after_substrate_headline_moved`
- joined 또는 no_state_change_join 헤드라인·동기화 집합에 진전 — 동일 상한으로 잔여 행·게이트 재점검.

## 번들 교차 참조 (closeout)

- `closeout_summary.gis_blocked_reason`: `concept_map_misses_for_sampled_raw_concepts`
- `state_change_join_refresh.state_change_run.run_id`: `223e2aa5-3879-4dee-b28f-3d579cbf4cbd` (scores_written 353)
- 초기 변위 참조 런 `state_change_run_id`: `39208f19-8d0e-4c35-9950-78963bb59a97` (initial scores_loaded 313)
- 상세 표·재현: `docs/phase35_evidence.md`
