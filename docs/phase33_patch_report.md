# Phase 33 패치 보고 — Forward coverage truth + price alignment

## 목적

Phase 32에서 **행 단위 forward 수리 건수**와 **`missing_excess_return_1q` 헤드라인**이 어긋나 읽히는 문제를 **결정적 진단**으로 분리하고, **`insufficient_price_history`** 에 대해 **가격 창 분류·결정적 일봉 백필·forward 재빌드**를 상한으로 수행한다. GIS는 **샘플 점검만**. 메타·광역 filing·임계·15/16·프리미엄·스코어 비목표.

## 수정 요약

| # | 영역 | 내용 |
|---|------|------|
| 1 | `market.price_ingest` | `run_market_prices_ingest_for_symbols` — 심볼 리스트·구간만 수집. |
| 2 | `phase33.phase32_bundle_io` | Phase 32 번들에서 터치 심볼·NQ `insufficient_price_history` 오류 추출. |
| 3 | `phase33.metric_truth_audit` | `report/export_forward_metric_truth_audit` — 심볼 큐 이탈·패널 행·joined 델타·헤드라인 괴리 설명. |
| 4 | `phase33.price_coverage` | 갭 리포트·`missing_market_prices_daily_window` 만 백필·recovered/deferred/blocked. |
| 5 | `phase33.forward_retry_after_price` | 오류 심볼 factor 패널 상한 `run_forward_returns_build_from_rows`. |
| 6 | `phase33.gis_narrow` | GIS `raw_present_no_silver` 개념맵 샘플·차단 사유. |
| 7 | `phase33.orchestrator` / `review` / `phase34_recommend` | `stage_semantics_truth`·번들·리뷰 MD·Phase 34 권고. |
| 8 | `main.py` | 위 CLI. |
| 9 | `src/tests/test_phase33_forward_coverage_truth.py` | 진실 분리·가격 분류·리뷰·retry 스킵. |

## 산출물

- `docs/operator_closeout/phase33_forward_coverage_truth_review.md`
- `docs/operator_closeout/phase33_forward_coverage_truth_bundle.json`

## 재현 예시

```bash
export PYTHONPATH=src
python3 src/main.py run-phase33-forward-coverage-truth \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase32-bundle-in docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --bundle-out docs/operator_closeout/phase33_forward_coverage_truth_bundle.json \
  --out-md docs/operator_closeout/phase33_forward_coverage_truth_review.md
```

## 실측 클로즈아웃 (2026-04-08, `sp500_current`)

- **근거**: `docs/operator_closeout/phase33_forward_coverage_truth_bundle.json`, 리뷰 MD 생성 UTC `2026-04-08T22:37:25+00:00`.
- **헤드라인 (Before→After 동일)**: `joined_recipe_substrate_row_count` 243, `thin_input_share` 1.0, `missing_excess_return_1q` 101, `missing_validation_symbol_count` 151, `missing_quarter_snapshot_for_cik` / `factor_panel_missing` 각 148.
- **`stage_semantics_truth`**: forward upsert op **5**건, **`symbol_cleared_from_missing_excess_queue_count` 0**, **joined Δ 0**, **가격 백필 repaired 0**, 터치 집합 excess-null 패널 행 **30/30**.
- **진실 감사**: Phase 32 번들상 `repaired_to_forward_present`=23과 달리, **라이브 검증 패널(터치 30 심볼)에서는 여전히 excess 컬럼이 전부 null**로 집계됨 → 심볼 큐 이탈 0과 정합. 헤드라인·큐는 **패널 행 단위 excess**와 동기화되어야 함.
- **가격 분류**: Phase 32 NQ `error_sample` 기준 **7건** 전부 **`lookahead_window_not_matured`** (63거래일 창·캘린더 성숙 부족) → `missing_market_prices_daily_window` 아님 → **일봉 백필 스킵**(`ingest_attempted: false`).
- **forward 재시도**: 오류 심볼 7개·factor 패널 7행 입력, **success_operations 5 / failures 9** (여전히 다수 `insufficient_price_history`).
- **GIS**: `blocked_unmapped_concepts_remain_in_sample`, 샘플 13개 concept 전부 `unmapped` (dei/us-gaap 혼합) — **대극모 맵 확장 없이 명시적 차단** 유지.
- **Phase 34** (번들 `phase34`): `continue_forward_and_price_coverage_with_truth_metrics` — 창 성숙 후 재측정·동일 상한 반복.

**후속**: Phase 34 실측 클로즈아웃 완료 — 전파 갱신으로 `missing_excess_return_1q` 101→78 등. **`docs/phase34_patch_report.md`**, **`docs/phase34_evidence.md`**, `docs/operator_closeout/phase34_forward_validation_propagation_bundle.json` 참고.

상세 표·표본·재현: **`docs/phase33_evidence.md`**.
