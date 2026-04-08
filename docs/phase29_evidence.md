# Phase 29 evidence

## Phase 29.1 (성능 핫픽스) 메모

- **원인**: `report_validation_registry_gaps` 의 CIK별 `fetch_ticker_for_cik` N+1 + `_snap()` 내 레지스트리 기반 리포트 중복 호출로 실 DB에서 초기 스냅 단계 정체 가능.
- **제거된 N+1**: `fetch_tickers_for_ciks` 배치 + 레지스트리에서 per-CIK 단건 조회 제거.
- **중복 감소**: 스냅 단계에서 `report_validation_registry_gaps` 는 **스냅당 1회**(전·후 `_snap` 합쳐 2회); 팩터·분기 스냅 갭 리포트는 사전 계산 결과를 재사용.
- **실행 성공 여부**: 패치 적용 후 아래 명령으로 운영자 acceptance — 완료 시 번들·리뷰 경로와 stdout 진행 태그를 증거로 남길 것.

## 재현 (오케스트레이션)

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 src/main.py run-phase29-validation-refresh-and-snapshot-backfill \
  --universe sp500_current \
  --panel-limit 8000 \
  --out-md docs/operator_closeout/phase29_validation_refresh_and_snapshot_backfill_review.md \
  --bundle-out docs/operator_closeout/phase29_validation_refresh_and_snapshot_backfill_bundle.json
```

## 개별 명령

- `report-stale-validation-metadata-flags` / `run-validation-refresh-after-metadata-hydration` / `export-stale-validation-metadata-rows`
- `report-quarter-snapshot-backfill-gaps` / `run-quarter-snapshot-backfill-repair` / `export-quarter-snapshot-backfill-targets`

## 수용 기준 (운영자가 번들로 채움)

워크오더: 아래 중 **하나라도** 실측에서 참이면 패치 성공으로 본다.

- `joined_market_metadata_flagged_count` 감소
- `validation_metadata_flags_cleared_count > 0`
- `missing_quarter_snapshot_for_cik` 감소 또는 분류가 actionable/deferred로 명확히 쪼개짐
- `missing_validation_symbol_count` 감소

해당 없으면 리뷰 MD **「수용 기준 대비」** 절에 다음 솔기가 명시된다.

## 로컬 테스트

```bash
pytest src/tests/test_phase29_validation_refresh.py src/tests/test_db_fetch_tickers_for_ciks.py -q
```

## 교차 참고

- Phase 28: `docs/phase28_evidence.md` (메타 수화 no-op 해소 전제)
