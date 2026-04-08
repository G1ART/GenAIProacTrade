# Phase 27 패치 보고 (Registry / metadata / temporal gap workorder)

## 목적

Phase 26에서 `targeted_data_backfill_next`로 확정된 블로커를 **좁은 진단·수리**로 분해한다. 제네릭 기판 스프린트·품질 임계 완화·Phase 15/16 강제·프리미엄·프로덕션 스코어링 변경은 하지 않는다.

## 구현 요약

| 항목 | 내용 |
|------|------|
| A 레지스트리 | `report-validation-registry-gaps` / `run-validation-registry-repair` / `export-validation-registry-gap-symbols` — `market_symbol_registry`·CIK·별칭·정규화 버킷 |
| B 메타데이터 | `report-market-metadata-gap-drivers` / `run-market-metadata-hydration-repair` / `export-market-metadata-gap-rows` — joined recipe + `missing_market_metadata` 플래그 |
| C Forward 성숙도 | `report-forward-gap-maturity` / `export-forward-gap-maturity-buckets` — 달력 프록시(고정 95일)로 `not_yet_matured` vs `true_repairable` 분리 |
| D State-change PIT | `report-state-change-pit-gaps` / `export-state-change-pit-gap-rows` / `run-state-change-history-backfill-repair`(확장 날짜 윈도우) |
| E 클로즈아웃 | `write-phase27-targeted-backfill-review` → `phase27_targeted_backfill_review.md` + 선택 번들 JSON |
| F Phase 28 | `recommend_phase28_branch` — 네 라벨 중 하나 |
| G 공통 코드 | `src/targeted_backfill/`, `db.records` 배치 조회, `run_market_metadata_hydration_for_symbols` |
| H 테스트 | `test_phase27_targeted_backfill.py` |

## 증거(운영자가 DB·CLI로 채움)

1. 레지스트리 버킷·수리 로그: `report-validation-registry-gaps`, `run-validation-registry-repair` stdout.
2. 메타 갭·수리: `report-market-metadata-gap-drivers`, `run-market-metadata-hydration-repair`.
3. Forward 성숙도·export: `report-forward-gap-maturity`, `export-forward-gap-maturity-buckets`.
4. PIT·선택 역사 백필: `report-state-change-pit-gaps`, 필요 시 `run-state-change-history-backfill-repair`.
5. 한 페이지 요약·번들: `write-phase27-targeted-backfill-review` → `docs/operator_closeout/phase27_targeted_backfill_review.md`, `phase27_targeted_backfill_bundle.json`.
6. 상세 실행 기록: `docs/phase27_evidence.md`.

## Phase 27.5 hotfix (corrective)

상세 패치 서술·실측 클로즈아웃은 전용 문서를 본다.

- `docs/phase27_5_hotfix_patch_report.md`
- `docs/phase27_5_hotfix_evidence.md`

요약: `fetch_cik_map_for_tickers` 청크 루프 대입 버그 수정; 번들 `rerun_readiness` 평면 정합·`wiring_warnings`; Phase28 `registry_gap_rollup`; registry repair 확장·`run-targeted-backfill-repair-and-review`; `test_phase27_5_hotfix.py`.

## 비목표

- 프리미엄 디스커버리 자동 오픈, 임계 자동 완화, 광범위 substrate 스프린트, 백테스트/UI/프로덕션 스코어 경로 변경.
