# HANDOFF — Phase 15 (Recipe Validation Lab)

## 현재 제품 위치

- **Phase 11–14**: 이전과 동일(트랜스크립트 seam, 공개 코어, 품질·잔차, 연구 엔진 커널).
- **Phase 15 (닫힘)**: **Recipe Validation Lab** — `recipe_validation_runs` / `recipe_validation_results` / `recipe_validation_comparisons` / `recipe_survival_decisions` / `recipe_failure_cases`. Phase 12–14 산출을 **소비**하되 **스코어·워치리스트 경로와 분리**.

## Phase 15로 가능해진 것

1. **리뷰가 있는** `candidate_recipe` 또는 `sandboxed` 가설에 대해 `run-recipe-validation`으로 결정적 검증 실행.
2. **명시 베이스라인 3종**: `state_change_score_only`, `naive_null`, `market_cap_inverse_rank` 대비 분위 스프레드 비교.
3. **코호트·연도 슬라이스** 결과를 `recipe_validation_results`에 적재; 비교는 `recipe_validation_comparisons`.
4. **생존 판정**(`survives` … `archive_failed`): `sandboxed`는 `survives` 불가, `thin_input`은 `survives` 캡, `failed`/`degraded` 품질은 상한 `demote_to_sandbox`.
5. **실패 메모리**(`recipe_failure_cases`): 코호트 열세·잔차 모순·thin_input 의존 등.
6. **스코어카드** JSON + Markdown: `export-recipe-scorecard`.

## 의도적으로 아직 없는 것

- 프리미엄 필수 입력, UI, 다지평, 자동 프로덕트 승격, 포트폴리오/체결.
- 검증 산출물을 `state_change.runner` 등 제품 스코어에 연결하지 않음(`research_validation` 문자열 미참조).

## 마이그레이션 (누적)

- **Phase 15**: `20250418100000_phase15_recipe_validation_lab.sql`

## 이 패치에서 “레시피가 살아남았는지”

**코드만으로는 판정하지 않음.** 운영 DB에서 `run-recipe-validation`을 돌린 뒤 `report-recipe-survivors`·`export-recipe-scorecard`로 **`survives`/`weak_survival` 존재 여부**를 확인해야 한다. 로컬/CI 테스트는 Mock·정책 단위이며 실제 표본 스프레드는 DB 데이터에 의존한다.

## 다음 단계 권장 (증거 기준)

1. **실 DB에서** 동일 프로그램 가설들에 검증을 한 번 이상 실행하고, 생존 분포를 본다.
2. **`survives`가 거의 없고** 대부분 `archive_failed`/`weak_survival`이면 → **공개 데이터 백필·패널 깊이·품질 `strong` 비율**을 올리는 쪽(Phase 15 워크오더의 “public expansion”).
3. **`contradictory_public_signal`·프리미엄 힌트**가 실패 건의 상당 부분을 차지하면 → **단일 프리미엄 ROI seam** PoC를 좁혀 검토.

---

## Phase 14 이전 요약

- `docs/phase14_evidence.md`, Phase 13 이하 문서 참고.
