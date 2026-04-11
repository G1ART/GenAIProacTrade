# Phase 35 evidence (measured closeout)

## 한줄 해석

Phase 34 **`synchronized` 23행**은 초기 조인에서 전부 **`state_change_not_built_for_row`**(당시 참조 `state_change` 런에 해당 CIK 점수 없음)로 **`no_state_change_join`**에 떨어졌다. **상한 `state_change_join_refresh`** 한 번으로 **23 CIK**를 재빌드한 뒤, 최종 변위는 **23행 전부 `included_in_joined_recipe_substrate` / `joined_now`**이다. **`joined_recipe_substrate_row_count`는 243→266**, **`no_state_change_join`은 31→8**(Phase 34 대비 +23 이탈분 회수). 미성숙 7심볼은 **격리 검증 OK**, **성숙 재시도 0**. GIS·가격 창은 **변화 없음(차단·스킵 유지)**. 부수적으로 **`joined_market_metadata_flagged_count`가 0→23**으로 올라갔다(확장된 joined 집합에 대한 메타 플래그).

## Run

- Command: `run-phase35-join-displacement-and-maturity`
- Universe: `sp500_current`
- Phase 34 bundle in: `docs/operator_closeout/phase34_forward_validation_propagation_bundle.json`
- Output bundle: `docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json`
- Review MD generated (UTC): `2026-04-09T04:53:34.557864+00:00`

## Headline substrate (Before → After, 번들 `before` / `after`)

| Field | Before | After |
|-------|--------|-------|
| joined_recipe_substrate_row_count | 243 | 266 |
| joined_market_metadata_flagged_count | 0 | 23 |
| thin_input_share | 1.0 | 1.0 |
| missing_excess_return_1q | 78 | 78 |
| no_state_change_join | 31 | 8 |
| missing_validation_symbol_count | 151 | 151 |
| missing_quarter_snapshot_for_cik | 148 | 148 |
| factor_panel_missing_for_resolved_cik | 148 | 148 |

### exclusion_distribution (after)

- missing_excess_return_1q: 78
- no_state_change_join: 8
- no_validation_panel_for_symbol: 151

## 가설 (동기화 23행 ↔ `no_state_change_join`)

| 시점 | `supported_by_counts` | `included_in_joined_recipe_substrate` | `excluded_no_state_change_join` |
|------|------------------------|----------------------------------------|----------------------------------|
| 초기 (`forward_validation_join_displacement_initial`, 런 `39208f19-8d0e-4c35-9950-78963bb59a97`, scores_loaded 313) | true | 0 | 23 |
| 최종 (`forward_validation_join_displacement_final`, 런 `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`, scores_loaded 353) | false | 23 | 0 |

- 초기 `join_seam_counts_on_synchronized_set`: **`state_change_not_built_for_row`: 23** (전부 동일 버킷).
- 최종 `join_seam_counts_on_synchronized_set`: **`joined_now`: 23**.

## state_change_join_refresh

- repair: `state_change_join_refresh_after_phase34`
- repair_target_row_count: 23
- distinct_ciks: 23개 (번들 `state_change_join_refresh.distinct_ciks` 참조)
- state_change_issuer_limit_used: 1940
- state_change_run: `run_id` `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`, status `completed`, scores_written 353, components_written 2118, warnings 142
- joined_recipe_unlocked_now_count: 23
- no_state_change_join_cleared_count: 23
- repaired_rows_count_on_synchronized_set: 23

## Displacement on synchronized set

- initial `displacement_counts`: `excluded_no_state_change_join`: 23
- final `displacement_counts`: `included_in_joined_recipe_substrate`: 23

## matured_window_schedule / forward retry

- expected_symbol_isolation_ok: true
- expected_symbols: MCK, MDT, MKC, MU, NDSN, NTAP, NWSA
- matured_eligible_now_count: 0, still_not_matured_count: 7
- matured_window_forward_retry: skipped, reason `no_immature_rows_became_would_compute_now`, forward_build skipped

## price_backfill_propagation_missing_window

- ingest_attempted: false
- note: `no_missing_market_prices_daily_window_in_propagation_rows`
- price_coverage_repaired_now_count: 0

## gis_deterministic_inspect

- cik 0000040704, symbol GIS
- outcome: `blocked_unmapped_concepts_remain_in_sample`
- blocked_reason: `concept_map_misses_for_sampled_raw_concepts`
- concepts_sampled: 13, unmapped_count: 13

## closeout_summary (요약 수치)

- validation_excess_filled_now_count: 23
- symbol_cleared_from_missing_excess_queue_count: 23
- joined_recipe_unlocked_now_count: 23
- no_state_change_join_cleared_count: 23
- gis_outcome: `blocked_unmapped_concepts_remain_in_sample`

## phase36

- phase36_recommendation: `continue_join_audit_after_substrate_headline_moved`
- rationale: joined 또는 no_state_change_join 헤드라인·동기화 집합에 진전 — 동일 상한으로 잔여 행·게이트 재점검.

## Reproduce

```bash
export PYTHONPATH=src
python3 src/main.py run-phase35-join-displacement-and-maturity \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase34-bundle-in docs/operator_closeout/phase34_forward_validation_propagation_bundle.json \
  --bundle-out docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --out-md docs/operator_closeout/phase35_join_displacement_and_maturity_review.md
```

## Related

- docs/phase35_patch_report.md
- HANDOFF.md (Phase 35.1, Phase 36)
- docs/phase34_evidence.md (선행 전파·동기화 23행 출처)
- docs/operator_closeout/phase35_join_displacement_and_maturity_review.md
- docs/phase36_evidence.md (후속 Phase 36 실측: 메타 23·잔여 SC 8·freeze)

## Tests

```bash
pytest src/tests/test_phase35_join_displacement_and_maturity.py -q
```
