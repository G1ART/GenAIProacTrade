# Phase 34 evidence (measured closeout)

## 한줄 해석

Phase 33에서 의심했던 **forward→validation 전파 누락**이 실측으로 확인되었고, **23개 패널 행**을 좁은 재빌드로 동기화하여 **`missing_excess_return_1q` 헤드라인이 101→78**로 감소했다. **`joined_recipe_substrate_row_count`는 243으로 정체**. NQ 잔여 7건은 전부 **창 미성숙**, 일봉 백필은 없음. GIS는 **차단 유지**.

## Run

- Command: `run-phase34-forward-validation-propagation`
- Universe: `sp500_current`
- Phase 32 bundle in: `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json`
- Output bundle: `docs/operator_closeout/phase34_forward_validation_propagation_bundle.json`
- Review MD generated (UTC): `2026-04-09T00:36:33.860962+00:00`

## Headline substrate (Before → After)

| Field | Before | After |
|-------|--------|-------|
| joined_recipe_substrate_row_count | 243 | 243 |
| thin_input_share | 1.0 | 1.0 |
| missing_excess_return_1q | 101 | 78 |
| missing_validation_symbol_count | 151 | 151 |
| missing_quarter_snapshot_for_cik | 148 | 148 |
| factor_panel_missing_for_resolved_cik | 148 | 148 |

### exclusion_distribution (after)

- missing_excess_return_1q: 78
- no_state_change_join: 31
- no_validation_panel_for_symbol: 151

(Before: missing_excess 101, no_state_change_join 8, no_validation_panel 151.)

## Propagation gap (touched 30 panel rows)

| Classification | Initial | After refresh / final |
|----------------|---------|------------------------|
| forward_present_validation_not_refreshed | 23 | 0 |
| forward_present_validation_refresh_failed | 0 | 0 |
| forward_not_present_window_not_matured | 7 | 7 |
| forward_not_present_other_gap | 0 | 0 |
| synchronized | 0 | 23 |

- forward_row_present_count (NQ excess non-null on forward table): 23 (unchanged across final gap; immature rows lack forward NQ row).

## validation_refresh

- target_factor_key_count: 23
- panels_refreshed: 23
- validation_panel_build: rows_upserted 23, failures 0
- validation_excess_filled_now_count: 23
- validation_excess_still_null_after_refresh_count: 0
- refresh_failed_keys: []

### metric_truth (touched set, before → after refresh)

- validation_panel_rows: excess_null **30→7**, excess_present **0→23**
- symbol_cleared_from_missing_excess_queue_count: **0→23**
- touched_symbols_still_in_missing_excess_queue: 7 symbols (MCK, MDT, MKC, MU, NDSN, NTAP, NWSA) — align with immature NQ rows
- missing_excess_return_1q_headline_live: **101→78**

## matured_forward_retry_targets

- source_error_row_count: 7
- maturity_eligible_count: 0
- still_not_matured_count: 7
- missing_market_prices_daily_window_count: 0
- registry_or_time_alignment_issue_count: 0
- run: skipped (`no_maturity_eligible_targets`), matured_forward_retry_success_count: 0

Symbols (same as Phase 33 NQ sample): MKC, NDSN, MU, MCK, NTAP, NWSA, MDT (signal dates in bundle).

## price_backfill_propagation_missing_window

- ingest_attempted: false
- note: no_missing_market_prices_daily_window_in_propagation_rows
- price_coverage_repaired_now_count: 0

## gis_deterministic_inspect

- cik 0000040704, symbol GIS
- outcome: blocked_unmapped_concepts_remain_in_sample
- blocked_reason: concept_map_misses_for_sampled_raw_concepts
- concepts_sampled: 13, unmapped_count: 13

## phase35

- phase35_recommendation: re_audit_forward_validation_join_and_schedule_matured_windows
- rationale: (see bundle) 기판·터치 전파에 진전 — 동일 상한 재감사 및 성숙 창만 후속 재시도.

## Reproduce

```bash
export PYTHONPATH=src
python3 src/main.py run-phase34-forward-validation-propagation \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase32-bundle-in docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --bundle-out docs/operator_closeout/phase34_forward_validation_propagation_bundle.json \
  --out-md docs/operator_closeout/phase34_forward_validation_propagation_review.md
```

## Related

- docs/phase34_patch_report.md
- HANDOFF.md (Phase 34)
- docs/phase33_evidence.md (prior sprint; excess-null-on-touch resolved in Phase 34 refresh)
- docs/operator_closeout/phase34_forward_validation_propagation_review.md
- docs/phase35_evidence.md (Phase 35 실측: 동기화 23행 state_change 이음새 수리·joined 243→266)

## Tests

```bash
pytest src/tests/test_phase34_forward_validation_propagation.py -q
```
