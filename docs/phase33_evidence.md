# Phase 33 evidence (measured closeout)

## 한줄 해석

헤드라인 지표는 변하지 않았고, truth 분리로 **터치 30 심볼 검증 패널은 라이브 기준 excess 전부 null**이라 **심볼 큐 이탈 0**이 설명 가능하다. 가격 샘플 7건은 **창 성숙 부족**만 있어 일봉 백필은 스킵되었고, forward 재시도는 **5성공/9실패** 부분 진행. GIS는 샘플 전부 unmapped로 **차단 명시**.

## Run

- Command: `run-phase33-forward-coverage-truth`
- Universe: `sp500_current`
- Phase 32 bundle in: `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json`
- Output bundle: `docs/operator_closeout/phase33_forward_coverage_truth_bundle.json`
- Review MD generated (UTC): `2026-04-08T22:37:25.854463+00:00`

## Headline substrate (Before = After)

| Field | Value |
|-------|-------|
| joined_recipe_substrate_row_count | 243 |
| thin_input_share | 1.0 |
| missing_excess_return_1q | 101 |
| no_validation_panel_for_symbol | 151 |
| no_state_change_join | 8 |
| missing_validation_symbol_count | 151 |
| missing_quarter_snapshot_for_cik | 148 |
| factor_panel_missing_for_resolved_cik | 148 |

## Quarter snapshot classification (end)

- no_filing_index_for_cik: 147
- raw_present_no_silver_facts: 1

## stage_semantics_truth

| Field | Value |
|-------|-------|
| forward_row_unblocked_now_count | 5 |
| symbol_cleared_from_missing_excess_queue_count | 0 |
| joined_recipe_unlocked_now_count | 0 |
| price_coverage_repaired_now_count | 0 |
| validation_panel_excess_null_rows_touched_set_live | 30 |

## metric_truth_audit (touched set, live)

- phase32_touched_symbol_count: 30
- validation_panel_rows: row_count 30, excess_null_row_count 30, excess_present_row_count 0
- Phase 32 bundle forward_row_unblocked_now_count_bundle_phase32: 23 (historical bundle field; live panel excess all null for this sample)

## Price coverage (7 rows from Phase 32 NQ error_sample)

All classified: lookahead_window_not_matured (MKC, NDSN, MU, MCK, NTAP, NWSA, MDT with signal dates in bundle).

- price_coverage_backfill: ingest_attempted false, note no_missing_market_prices_daily_window_targets

## forward_return_retry_after_price_repair

- symbols_from_phase32_errors: 7 (MCK, MDT, MKC, MU, NDSN, NTAP, NWSA)
- factor_panels_input: 7
- forward_build: success_operations 5, failures 9
- joined_recipe_unlocked_delta_after_retry: 0
- symbol_queue_cleared_delta_after_retry: 0

## gis_deterministic_inspect

- cik 0000040704, symbol GIS
- outcome: blocked_unmapped_concepts_remain_in_sample
- concepts_sampled: 13, unmapped_count: 13

## phase34 (Phase 33 번들 권고)

- phase34_recommendation: continue_forward_and_price_coverage_with_truth_metrics

**업데이트**: Phase 34 스프린트 실행 후 터치 집합 **validation excess 동기화 23행**, 헤드라인 `missing_excess_return_1q` **101→78**. 근거: **`docs/phase34_evidence.md`**, **`docs/phase34_patch_report.md`**.

## Reproduce

```bash
export PYTHONPATH=src
python3 src/main.py run-phase33-forward-coverage-truth \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase32-bundle-in docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --bundle-out docs/operator_closeout/phase33_forward_coverage_truth_bundle.json \
  --out-md docs/operator_closeout/phase33_forward_coverage_truth_review.md
```

## Related

- docs/phase33_patch_report.md
- HANDOFF.md (Phase 33)
- docs/operator_closeout/phase33_forward_coverage_truth_review.md

## Tests

```bash
pytest src/tests/test_phase33_forward_coverage_truth.py -q
```
