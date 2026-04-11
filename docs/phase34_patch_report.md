# Phase 34 패치 보고 — Forward→validation propagation + maturity-aware retry

## 목적

Phase 33에서 확인된 이음새(forward `next_quarter` excess는 DB에 있는데 `factor_market_validation_panels.excess_return_1q`는 null)를 결정적 감사·분류하고, 해당 행만 `run_validation_panel_build_from_rows`로 좁게 갱신한다. Phase 32 NQ `insufficient_price_history`에는 `would_compute_now`(성숙)만 forward 재시도하고, 전파 감사상 `missing_market_prices_daily_window`만 일봉 수집한다. GIS·메타·광역 filing·임계·15/16·스코어 비목표.

## 수정 요약

| # | 영역 | 내용 |
|---|------|------|
| 1 | `phase34.propagation_audit` | 터치 심볼 패널 행 단위 forward vs validation excess·가격 분류. |
| 2 | `phase34.validation_refresh` | `forward_present_validation_not_refreshed` → factor 패널 조회 후 validation 재빌드. |
| 3 | `phase34.matured_forward_retry` | 성숙 타깃 리포트·`run_matured_forward_retry`. |
| 4 | `phase34.price_backfill` | 전파 행 중 missing_window만 `run_market_prices_ingest_for_symbols`. |
| 5 | `phase34.orchestrator` / `review` / `phase35_recommend` | 일괄 런·번들·리뷰 MD·Phase 35 권고. |
| 6 | `main.py` | 전파 report/export, validation refresh, matured report/export·run, phase34 orchestrator, review writer. |
| 7 | `src/tests/test_phase34_forward_validation_propagation.py` | 분류·refresh 스킵·성숙 스킵·가격·오케스트레이터 스모크. |

## 산출물

- `docs/operator_closeout/phase34_forward_validation_propagation_review.md`
- `docs/operator_closeout/phase34_forward_validation_propagation_bundle.json`

## 재현 예시

```bash
export PYTHONPATH=src
python3 src/main.py run-phase34-forward-validation-propagation \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase32-bundle-in docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --bundle-out docs/operator_closeout/phase34_forward_validation_propagation_bundle.json \
  --out-md docs/operator_closeout/phase34_forward_validation_propagation_review.md
```

## 실측 클로즈아웃 (2026-04-09, sp500_current)

- **근거**: 위 번들·리뷰 MD 생성 UTC `2026-04-09T00:36:33+00:00`.
- **병목 판단**: 가격 일봉 부족이 아니라 **validation 패널이 forward 결과를 반영하지 않은 전파 지연**이 맞았다. 초기 감사에서 터치 30행 중 23행이 `forward_present_validation_not_refreshed`, 7행이 `forward_not_present_window_not_matured`. refresh 후 미전파 23→0, `synchronized` 23, `refresh_failed` 0.
- **헤드라인**: `joined_recipe_substrate_row_count` 243→243, `thin_input_share` 1.0, **`missing_excess_return_1q` 101→78**, 나머지 검증·스냅·팩터 헤드라인 151/148/148 유지.
- **제외 분포**: `no_state_change_join` 8→31 (excess 채운 뒤 recipe join에서 막히는 발행인이 집계상 증가).
- **validation refresh**: 대상 23키, upsert 23, 실패 0, `validation_excess_filled_now_count` 23. 터치 패널 excess null 30→7, present 0→23; `symbol_cleared_from_missing_excess_queue_count` 0→23.
- **성숙 forward 재시도**: NQ 오류 7건 전부 `lookahead_window_not_matured`, eligible 0, 재시도 스킵.
- **가격 백필**: missing_window 대상 없음, repaired 0.
- **GIS**: `blocked_unmapped_concepts_remain_in_sample` 유지.
- **Phase 35**: `re_audit_forward_validation_join_and_schedule_matured_windows`.

상세: **`docs/phase34_evidence.md`**.

**후속**: Phase 35 — joined 변위·state_change 이음새·성숙 스케줄. **`docs/phase35_patch_report.md`**, `run-phase35-join-displacement-and-maturity`. **실측(2026-04-09)**: 동기화 23행이 `state_change_join_refresh` 후 전부 joined; `joined_recipe_substrate_row_count` 243→266, `no_state_change_join` 31→8 — **`docs/phase35_evidence.md`**.
