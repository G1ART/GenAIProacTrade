# Phase 30 패치 보고 — Upstream validation substrate repair

## 목적

Phase 29 이후 잔존하는 **`missing_validation_symbol_count`** / **`missing_quarter_snapshot_for_cik`** 의 주 원인을 **상류 SEC 기판**(filing_index, raw/silver XBRL, 분기 스냅샷)으로 좁혀, **상한 있는 수리**와 **수리된 CIK에만** 하류(스냅샷→팩터→검증) 연쇄를 수행한다. 메타 프로바이더 재개방·임계 완화·Phase 15/16 강제·프리미엄·프로덕션 스코어 변경 없음.

## 수정 요약

| # | 영역 | 내용 |
|---|------|------|
| 1 | `phase30.metrics` | `collect_validation_substrate_snapshot` — 번들용 지표(검증 심볼, 분기 스냅 갭, 분류 counts, factor_panel_missing, joined_row_count, thin_input_share). |
| 2 | `phase30.filing_index_gaps` | Phase 29 분류에서 `no_filing_index_for_cik` 추출; `run_sample_ingest`로 filing_index 보강; repaired / deferred / blocked 버킷. |
| 3 | `phase30.silver_materialization` | `raw_present_no_silver_facts` 대상 raw→silver 적재; 가능 시 `rebuild_quarter_snapshot_from_db`; 분류 before/after. |
| 4 | `phase30.empty_cik_cleanup` | 멤버십·registry·issuer map 진단(v1 DB 변경 없음). |
| 5 | `phase30.downstream_cascade` | 전달된 CIK만 스냅샷 갭 메우기 → `run_factor_panels_for_cik` → `run_validation_panel_build_from_rows`. |
| 6 | `phase30.phase31_recommend` | 단일 Phase 31 권고 문자열. |
| 7 | `phase30.orchestrator` | 전·후 스냅샷 + A/B/C + cascade + 번들. |
| 8 | `phase30.review` | `phase30_validation_substrate_review.md`. |
| 9 | `main.py` | 위 CLI 등록 (`p27` parents). |
| 10 | `src/tests/test_phase30_validation_substrate.py` | 버킷·silver·empty_cik·cascade·phase31·리뷰. |

## 산출물 (운영자 실행 후)

- `docs/operator_closeout/phase30_validation_substrate_review.md`
- `docs/operator_closeout/phase30_validation_substrate_bundle.json` (`--bundle-out` 로 경로 지정 가능)

## 재현 예시

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 -u src/main.py run-phase30-validation-substrate-repair \
  --universe sp500_current \
  --panel-limit 8000 \
  --out-md docs/operator_closeout/phase30_validation_substrate_review.md \
  --bundle-out docs/operator_closeout/phase30_validation_substrate_bundle.json
```
