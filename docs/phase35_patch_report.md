# Phase 35 패치 보고 — Join displacement + state_change seam + maturity schedule

## 목적

Phase 34 이후 **`joined_recipe_substrate_row_count` 정체**와 **`no_state_change_join` 증가**를 **동기화 23행** 기준으로 `compute_substrate_coverage`와 동일한 PIT 조인 규칙으로 추적한다. **state_change** 상한 재실행·**미성숙 7심볼** 스케줄·좁은 가격·GIS는 워크오더 비목표 범위를 유지한다.

## 모듈·CLI

| 구역 | 내용 |
|------|------|
| `phase35.join_displacement` | `report/export_forward_validation_join_displacement` |
| `phase35.state_change_join_gaps` | `report_state_change_join_gaps_after_phase34` |
| `phase35.state_change_refresh` | `run_state_change_join_refresh_after_phase34` (`state_change_not_built_for_row` 만) |
| `phase35.matured_window_schedule` | 스케줄 리포트·export·`run_matured_window_forward_retry_for_phase34_immature` |
| `phase35.orchestrator` | `run_phase35_join_displacement_and_maturity` |
| `phase35.review` / `phase36_recommend` | 클로즈아웃 MD·JSON·Phase 36 권고 |
| `main.py` | 위 서브커맨드 |

## 산출물

- `docs/operator_closeout/phase35_join_displacement_and_maturity_review.md`
- `docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json`

## 재현

```bash
export PYTHONPATH=src
python3 src/main.py run-phase35-join-displacement-and-maturity \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase34-bundle-in docs/operator_closeout/phase34_forward_validation_propagation_bundle.json \
  --bundle-out docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --out-md docs/operator_closeout/phase35_join_displacement_and_maturity_review.md
```

## 테스트

`pytest src/tests/test_phase35_join_displacement_and_maturity.py -q`

## 실측 (sp500_current, 2026-04-09)

- **증거**: `docs/phase35_evidence.md`, `docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json`, `phase35_join_displacement_and_maturity_review.md` (생성 UTC `2026-04-09T04:53:34.557864+00:00`).
- **기판**: `joined_recipe_substrate_row_count` **243→266**, `no_state_change_join` **31→8**, `missing_excess_return_1q` **78 유지**.
- **동기화 23행**: 초기 전부 `state_change_not_built_for_row` → `excluded_no_state_change_join`; `state_change_join_refresh` 후 최종 전부 `included_in_joined_recipe_substrate` / `joined_now`. 참조 런: 이전 `39208f19-8d0e-4c35-9950-78963bb59a97`(scores_loaded 313), 수리 후 `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`(scores_written 353).
- **7심볼**: 격리 OK, `matured_eligible_now_count` 0, forward retry 스킵.
- **가격·GIS**: 전파 행 가격 갭 없음; GIS **차단 유지** (`concept_map_misses_for_sampled_raw_concepts`).
- **부수**: `joined_market_metadata_flagged_count` **0→23**.
- **Phase 36 후속**: 번들 권고는 `continue_join_audit_after_substrate_headline_moved`. **실측(2026-04-10)**: Phase 36 오케스트레이터 — **`docs/phase36_evidence.md`**.
