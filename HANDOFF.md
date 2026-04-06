# HANDOFF — Phase 16 (Validation Campaign Orchestrator)

## 현재 제품 위치

- **Phase 11–15**: 이전과 동일(공개 코어, 연구 엔진, 가설 단위 Recipe Validation Lab).
- **Phase 16 (본 패치)**: **프로그램 단위 검증 캠페인** — 자격 있는 가설에 대해 Phase 15 검증을 **호환 시 재사용**·아니면 실행하고, 생존·실패·프리미엄 힌트를 집계해 **단일 전략 권고**(`public_data_depth_first` \| `targeted_premium_seam_first` \| `insufficient_evidence_repeat_campaign`)를 DB와 JSON+Markdown 브리프로 남긴다. **제품 스코어·워치리스트와 분리**(`validation_campaign` 미연동).

## Phase 16으로 가능해진 것

1. **`list-eligible-validation-hypotheses`**: `candidate_recipe`/`sandboxed` + 리뷰 + 심판 + 비아카이브 프로그램만 나열.
2. **`run-validation-campaign`**: `reuse_only` \| `reuse_or_run` \| `force_rerun`; `recipe_validation_runs.join_policy_version` 등으로 **pre/post Phase 15 조인 혼입 방지**.
3. **`report-program-survival-distribution`**: 프로그램 소속 가설의 **최근 완료 검증** 기준 생존 분포.
4. **`export-validation-decision-brief`**: 권고·근거·집계·반증 시 행동을 **결정적 아티팩트**로 출력.
5. **증거 게이트**: 캠페인 집계가 **다음 전략 분기**(공개 데이터 깊이 vs 좁은 프리미엄 seam vs 캠페인 재실행)를 **코드 정책**으로 제안한다(수동 vibe 대체).

## 의도적으로 아직 없는 것

- 라이브 프리미엄 seam, 광범위 백필 본체, UI, 다프로그램 최적화, 승격 자동화, 다지평, 체결 추천.

## 마이그레이션 (누적)

- **Phase 16**: `20250419100000_phase16_validation_campaign.sql` (`validation_campaign_*` + `recipe_validation_runs.join_policy_version` 백필)

## 다음 단계 권장 (캠페인 증거 기준)

1. Supabase에 Phase 16 마이그레이션 적용 후 `smoke-phase16-validation-campaign` 확인.
2. 잠금 프로그램 UUID로 `run-validation-campaign --run-mode reuse_or_run` 실행 → `export-validation-decision-brief`로 권고 확인.
3. 권고가 **`public_data_depth_first`**이면(현재 thin_input·weak_survival 패턴과 정합) **공개 코어/패널/품질 깊이** 확장을 다음 작업 헤드라인으로 둔다.
4. 권고가 **`targeted_premium_seam_first`**로 바뀌는 집계(강한 기판에서 잔차·프리미엄 실패 집중)가 나오면 **단일 프리미엄 ROI seam** PoC를 헤드라인으로 둔다.
5. **`insufficient_evidence_repeat_campaign`**이면 가설·검증 다양성을 늘린 뒤 캠페인 재실행.

---

## Phase 15 이전 요약

- `docs/phase15_evidence.md`, Phase 14 이하 문서 참고.
