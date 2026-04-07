# Phase 25 패치 보고 (2026-04-07 workorder)

## 목적

오케스트레이션 추가가 아니라 **공개 기판(substrate) 커버리지**를 좁혀 `thin_input_share`와 지배적 제외(`no_validation_panel_for_symbol`, `missing_excess_return_1q`, `no_state_change_join`)를 줄인다.

## 구현 요약

| 영역 | 내용 |
|------|------|
| A 검증 패널 | `report-validation-panel-coverage-gaps`, `run-validation-panel-coverage-repair` — 원인 버킷·누락 심볼·전후 `missing_symbol_count` |
| B 선행 excess | `report-forward-return-gaps`, `run-forward-return-backfill` — 행 단위 원인·`run_forward_returns_build_from_rows` 타깃 백필 |
| C state join | `report-state-change-join-gaps`, `run-state-change-join-repair` — PIT 조인 실패 분류·`run_state_change` 재실행 |
| D 스코어보드 | `write-substrate-closure-review` 또는 `run-substrate-closure-sprint` → `docs/operator_closeout/substrate_closure_review.md` |
| E 게이트 | `report-substrate-closure-snapshot` / 스프린트 종료 시 Phase 15·16 `opened` vs `still blocked` + 블로커 문구 |
| F 트레이드오프 | 각 `run-*-repair` JSON의 `tradeoffs.silent_degradation`·`secondary_metrics_worsened` |
| G 테스트 | `src/tests/test_phase25_substrate_closure.py` (진단·수리 델타·스코어보드·PIT·이중 집계·경계) |

## 증거(운영자가 DB에서 채움)

1. 세 지배 제외 **before/after 행 수**: 스냅샷 `exclusion_distribution` 또는 리뷰 MD 표.
2. **thin_input_share** / **joined_recipe_substrate_row_count**: 동일.
3. **Rerun 게이트**: `recommend_rerun_phase15` / `recommend_rerun_phase16`.
4. **프로덕션 스코어링 경계**: `substrate_closure` 패키지가 `hypothesis_registry` / `research_engine` / `validation_campaign` / `public_repair_campaign` 문자열을 소스에 포함하지 않음(테스트 `test_substrate_closure_package_does_not_import_research_pipeline_wiring`).
5. **Phase 26 권고**: 리뷰 MD의 `recommend_phase26_from_gates` 문장(게이트 열림 → 15/16 재실행 검토, 아니면 기판 스프린트 연장).

## 비목표 (준수)

- 프리미엄 자동 오픈·라이브 프리미엄 통합 없음.
- 백테스트·포트폴리오·UI·추가 거버넌스 레이어 없음.
