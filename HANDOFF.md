# HANDOFF — Phase 27 (Targeted backfill: registry, metadata, maturity, PIT)

## 현재 제품 위치

- **Phase 27 (본 패치)**: Phase 26에서 확정한 블로커를 **좁은 진단·수리**로 분해한다. **제네릭 기판 스프린트·임계 완화·Phase 15/16 강제·프리미엄 오픈·프로덕션 스코어 변경 없음**.
- **CLI** (`--universe`, `--panel-limit`, `--program-id`, `--price-lookahead-days` 등):  
  - `report-validation-registry-gaps` / `run-validation-registry-repair` / `export-validation-registry-gap-symbols`  
  - `report-market-metadata-gap-drivers` / `run-market-metadata-hydration-repair` / `export-market-metadata-gap-rows`  
  - `report-forward-gap-maturity` / `export-forward-gap-maturity-buckets` (`--eval-date` 선택)  
  - `report-state-change-pit-gaps` / `export-state-change-pit-gap-rows` / `run-state-change-history-backfill-repair` (`--history-backfill-days`, `--state-change-limit`)  
  - `write-phase27-targeted-backfill-review` → `docs/operator_closeout/phase27_targeted_backfill_review.md` (선택 `--bundle-out` JSON)
- **코드**: `src/targeted_backfill/`, `db.records`(레지스트리·메타·멤버십 배치 조회), `market.price_ingest.run_market_metadata_hydration_for_symbols`.
- **실측 수치**: 저장소만으로 고정 숫자 없음 — 운영자가 위 report/export 및 리뷰 작성으로 **증거·수리 후 블로커 카운트**를 채운다.
- **Phase 28 권고(정확히 하나)**: 번들/stdout의 `phase28` — `rerun_phase15_16_now_open` \| `continue_targeted_backfill` \| `quality_policy_review_needed` \| `public_first_plateau_without_quality_unlock`.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase27_targeted_backfill.py -q`

---

# HANDOFF — Phase 26 (Thin-input root cause: drivers, repair audit, exports)

## 현재 제품 위치

- **Phase 26 (본 패치)**: Phase 25가 **제로 델타**였던 환경에서, `thin_input_share=1.0`이 **사이클 품질 정책(Phase 13)** 축인지 **기판 제외 축**인지 분해하고, Phase 25 수리 경로의 **no-op 여부**를 감사한다. **거버넌스·프리미엄 자동 오픈·임계 자동 완화 없음**.
- **CLI** (`--universe`, `--panel-limit`, `--program-id latest`, `--quality-run-lookback`):  
  - `report-thin-input-drivers` — thin 사이클 드라이버 + **joined recipe** 행의 `panel_json` 플래그 분해  
  - `report-validation-repair-effectiveness` / `report-forward-backfill-effectiveness` / `report-state-change-repair-effectiveness`  
  - `export-unresolved-validation-symbols` / `export-unresolved-forward-return-rows` / `export-unresolved-state-change-joins` (`--out`, `--format json|csv`)  
  - `report-quality-threshold-sensitivity` — **검토 전용** 가상 임계 시나리오 (`no_automatic_threshold_mutation`)  
  - `write-thin-input-root-cause-review` → `docs/operator_closeout/thin_input_root_cause_review.md` (선택 `--bundle-out` JSON)  
  - `report-thin-input-root-cause-bundle` — 단일 JSON 번들
- **코드**: `src/thin_input_root_cause/`, `public_depth.diagnostics.compute_substrate_coverage(..., joined_panels_out=)`, `db.records.fetch_ingest_runs_by_run_types_recent` / `fetch_state_change_runs_for_universe_recent`.
- **1차 블로커 분류 (리뷰 번들)**: `data_absence` \| `join_logic` \| `quality_policy` \| `mixed` — joined 행이 전부 `panel_json` 깨끗하고 thin 사이클이 지속되면 **quality_policy** 쪽으로 기울어 분류.
- **광범위 기판 스프린트**: 검증·forward 효과 감사에서 `likely_no_op: true`가 동시에면 **또 다른 제네릭 스프린트는 비효율 가능성이 높다**고 리뷰 MD에 명시.
- **Phase 27 권고(정확히 하나)**: `targeted_data_backfill_next` \| `quality_policy_review_needed` \| `rerun_phase15_16_now_open` \| `public_first_plateau_without_quality_unlock` — 번들의 `phase27` 필드.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase26_thin_input_root_cause.py -q`

## 패치 보고·증거

- `docs/phase26_patch_report.md`
- 실측 클로즈아웃 실행 기록·산출물 목록: `docs/phase26_evidence.md` (`docs/operator_closeout/thin_input_root_cause_review.md`, `phase26_root_cause_bundle.json`, 미해결 export 3종)

---

# HANDOFF — Phase 25 (Substrate closure: validation / forward / state-change join)

## 현재 제품 위치

- **Phase 25 (본 패치)**: Phase 24 증거에서 드러난 **기판 병목**(`thin_input_share`, `no_validation_panel_for_symbol`, `missing_excess_return_1q`, `no_state_change_join`)을 **진단·타깃 수리**한다. **거버넌스 레이어 추가 없음**, **프리미엄 디스커버리·라이브 통합 자동 오픈 없음**.
- **CLI (유니버스·`--panel-limit`·선택 `--program-id latest`)**  
  - `report-validation-panel-coverage-gaps` / `run-validation-panel-coverage-repair`  
  - `report-forward-return-gaps` / `run-forward-return-backfill`  
  - `report-state-change-join-gaps` / `run-state-change-join-repair`  
  - `report-substrate-closure-snapshot` — 메트릭+제외+`build_revalidation_trigger` 스냅샷 JSON  
  - `write-substrate-closure-review` — before/after JSON → `docs/operator_closeout/substrate_closure_review.md`  
  - `run-substrate-closure-sprint` — `--repair-validation` / `--repair-forward` / `--repair-state-change` 선택 + `--refresh-validation-after-forward` + 리뷰 MD·선택 `--out-stem` JSON
- **코드**: `src/substrate_closure/`, `src/market/validation_panel_run.py`(`run_validation_panel_build_from_rows`), `src/market/forward_returns_run.py`(`run_forward_returns_build_from_rows`).
- **실 DB before/after 숫자**: 이 저장소 패치만으로는 고정치가 없음 — 운영자가 스프린트 전후 `report-substrate-closure-snapshot` 또는 스프린트 JSON으로 **실측 델타**를 채운다.
- **Rerun 게이트(Phase 15/16)**: 스냅샷의 `recommend_rerun_phase15` / `recommend_rerun_phase16` 및 스프린트 종료 시 stdout `=== Rerun readiness (after sprint) ===` 로 확인. **열리지 않았다면** `joined_recipe_substrate_row_count`·`thin_input_share` 임계(`public_buildout.constants`)가 블로커.
- **프리미엄 리뷰**: **여전히 공개 우선 기본** — 자동 프리미엄 오픈 없음; `substrate_closure_review.md`에 Premium 섹션 명시.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase25_substrate_closure.py -q`

## 패치 보고·증거

- `docs/phase25_patch_report.md`

---

# HANDOFF — Phase 24 (Public-first empirical layer)

## 현재 제품 위치

- **Phase 24 (본 패치)**: 반복 공개 우선 운영을 **집계·판독 가능한 경험층**으로 올린다. **`report-public-first-branch-census`**, **`export-public-first-branch-census-brief`**, **`export-public-first-plateau-review-brief`** / **`run-public-first-plateau-review`**, **`advance-public-first-cycle`**(교대 리듬 + 혼합 시 Phase 23 chooser 위임). 결론 타입: `public_first_still_improving` \| `mixed_or_insufficient_evidence` \| `premium_discovery_review_preparable`(리뷰 전용, **라이브·자동 프리미엄 오픈 없음**). 산출: `docs/operator_closeout/latest_public_first_review.md` 등.
- **포함/제외 위생**: 기본 **정책 버전 불일치 시리즈 제외**, **인프라 실패 런 제외(플래토와 동일)**, **동일 repair/depth 런 ID 중복 집계 제외**, **closed 시리즈는 옵션으로만**(`--include-closed-series`).
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` + `test_phase24_public_first`).

## Phase 24로 가능해진 것

1. 다중 호환 시리즈에 대한 **브랜치·신호·개선 분류 집계** + 제외 사유 목록
2. **플래토 리뷰 결론** 3종 (프리미엄은 *preparable* 만, 자동 오픈 없음)
3. **교대 코디네이터**: 개선 증거가 명확하면 마지막 멤버 기준 repair↔depth 교대, 아니면 Phase 23 chooser

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase24_public_first.py -q`
- 전체: `pytest src/tests -q` — **337 passed** (Phase 27 포함)

## 관측 분포·정책 자세 (2026-04-07, `sp500_current`, Phase 23 클로즈아웃 직후 맥락)

| 관측 | 해석 |
|------|------|
| 클로즈아웃 chooser | `advance_repair_series`, 에스컬레이션 `hold_and_repeat_public_repair`, 신호 `repeat_targeted_public_repair` |
| **프리미엄 디스커버리 리뷰** | **아직 preparable 아님** — 활성 에스컬레이션이 `open_targeted_premium_discovery` 가 아님(리뷰 “획득” 전) |
| **공개 우선 궤도** | **유지** — 수리 반복 쪽 가중이나 공개 스택·시리즈는 계속 운용 |
| **Plateau review 결론(코드 규칙)** | depth 분류 표본이 부족하거나 혼재 시 **`mixed_or_insufficient_evidence`**; 다회 `meaningful_progress`+`marginal_progress` 다수 시 **`public_first_still_improving`** — **실 DB에서** `export-public-first-plateau-review-brief` 로 확정 |

## 마이그레이션 (누적)

- **새 DDL 없음**(Phase 24는 집계·CLI·리뷰 문서).

## 패치 보고·증거

- `docs/phase24_patch_report.md`
- `docs/phase24_evidence.md`

---

# HANDOFF — Phase 23 (One-command post-patch closeout)

## 현재 제품 위치

- **Phase 23 (본 패치)**: 패치 후 클로즈아웃을 **`run-post-patch-closeout --universe U`** 한 번으로 수행한다. **정상 경로에서 운영자는 시리즈 UUID를 조회·복붙할 필요가 없다**(내부 ID는 `latest_closeout_summary.md`·JSON 산출물에 감사용으로 남음). **`report-required-migrations`**, **`verify-db-phase-state`**, **`export-public-depth-series-brief`** 의 무 UUID 운영 모드(`--program-id`+`--universe`, `--series-id` 생략), 결정적 **`choose_post_patch_next_action`**(verify_only / advance_repair / advance_depth / hold_plateau). **프리미엄 디스커버리 자동 오픈 없음** — 에스컬레이션 `open_targeted_premium_discovery` 는 **hold_for_plateau_review** 로만 처리.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` + `test_phase23_operator_closeout`).

## Phase 23로 가능해진 것

1. **`run-post-patch-closeout`** — 마이그레이션 리포트(가능 시) → phase17–22 스모크 → 시리즈 자동 해석·오픈 슬롯 생성 → 전진·브리프·요약 MD
2. **`report-required-migrations`** / **`--write-bundle`** — 누락 파일명·순서·사유·선택적 SQL 번들
3. **`verify-db-phase-state`** — 단일 명령 스모크 체인
4. **프리셋** — `.operator_closeout_preset.json` 또는 `docs/operator_closeout_preset.example.json` 참고
5. **브리프 export 무 UUID** — `export-public-depth-series-brief` + latest + universe

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase23_operator_closeout.py -q`
- 전체: `pytest src/tests -q` — **337 passed** (Phase 27 포함) (Phase 24 포함; 외부 `edgar` DeprecationWarning만)

## 검증·운영 스냅샷 (2026-04-07, `sp500_current`, 원 커맨드 클로즈아웃)

| 항목 | 결과 |
|------|------|
| `run-post-patch-closeout --universe sp500_current` | 완료; 요약 `docs/operator_closeout/latest_closeout_summary.md` |
| `schema_migrations` API 프로브 | 미노출(`PGRST106`) — **스모크가 스키마 진실로 전부 통과** |
| phase17–22 스모크 | **통과** |
| 시리즈 해석 | `active_compatible_series` (UUID는 요약·JSON에만 감사 기록) |
| 자동 전진 | `advance_repair_series` **성공**; 브리프 `docs/operator_closeout/closeout_advance_repair.*`, `closeout_depth_series_brief.*` |
| 운영자 추가 **필수** 액션 | **없음** — 브리프 검토·다음 주기 판단은 선택 |
| 증거 상세 | `docs/phase23_evidence.md` |

**다음 담당자:** 다음 패치 후 동일 명령으로 재클로즈. 마이그레이션 이력을 API로 맞추고 싶다면 Supabase 대시보드에서 별도 확인(프로브 실패만으로는 스모크를 대체하지 않음).

## 마이그레이션 (누적)

- Phase 22까지 SQL 파일은 기존과 동일; **새 DDL 없음**(Phase 23은 오케스트레이션·CLI만).

## 패치 보고·증거

- `docs/phase23_patch_report.md`
- `docs/phase23_evidence.md` — 실측 클로즈아웃·PGRST106 설명·필수 후속 없음 명시
- 정상 운영 절차: `docs/OPERATOR_POST_PATCH.md` (상단 3스텝 + 부록)

---

# HANDOFF — Phase 22 (Public-depth iteration evidence)

## 현재 제품 위치

- **Phase 11–21**: 이전과 동일(선택자·라이프사이클·인프라 격리·`advance-public-repair-series`·에스컬레이션 브리프 v2).
- **Phase 22 (본 패치)**: 동일 `public_repair_iteration_series` 아래에 **공개 깊이 확장 런**을 `member_kind=public_depth` 멤버로 적재하고, **`phase22_ledger`**(thin/joined/제외/준비도/rerun 게이트/빌드 액션/개선 분류)를 남긴다. **`advance-public-depth-iteration`** 골든 패스, **`export-public-depth-series-brief`** 다회 증거 요약, 에스컬레이션 위에 **`public_depth_operator_signal`**(continue buildout / repeat targeted repair / near-plateau review)을 얹는다. **프리미엄 디스커버리 자동 오픈·라이브 통합 없음**; Phase 15/16 재검증 캠페인은 **`--execute-phase15-16-revalidation`** 이고 게이트가 **새로 열린 경우에만** 실행.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` 테스트 유지).

## Phase 22로 가능해진 것

1. **`smoke-phase22-public-depth-iteration`** — 멤버 스키마( `member_kind`, `public_depth_run_id` ) 도달
2. **`advance-public-depth-iteration`** — 활성 시리즈(없으면 생성) → readiness/trigger 스냅샷 → `run_public_depth_expansion` → ledger·멤버 append(동일 `public_depth_run_id` 멱등) → 플래토·에스컬레이션·depth 신호·depth+repair 브리프
3. **`export-public-depth-series-brief`** — 런 수, 포함/제외, 개선 분류 분포, 저장된 에스컬레이션 브랜치 카운트, 최종 권고, 미해결 제외 힌트
4. **`marginal_policy` / `depth_signal`** — 투명 임계값 기반 `improvement_classification` 및 운영자 신호
5. 플래토 수집 경로에서 **`public_depth_runs` 실패·인프라 패턴 제외**(기본)

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase22_public_depth_iteration.py -q` — **15 passed**
- `pytest src/tests -q` — **337 passed** (Phase 27까지; 외부 `edgar` DeprecationWarning 3건)

## 검증·운영 스냅샷 (2026-04-01, 시리즈 브리프 + 전체 테스트 클로징)

| 항목 | 결과 |
|------|------|
| `pytest src/tests/test_phase22_public_depth_iteration.py -q` | **15 passed** |
| `PYTHONPATH=src pytest src/tests -q` | **337 passed** (Phase 27까지); 경고 **3건**은 `edgar` 패키지 deprecation(테스트 실패 아님) |
| Supabase `20250425100000_phase22_public_depth_iteration.sql` | 대상 프로젝트에 적용했다면 `smoke-phase22-public-depth-iteration`으로 REST/스키마 확인 |
| 시리즈 브리프 | `report-latest-repair-state --program-id latest --universe <U> --active-series-id-only`로 얻은 UUID로 `export-public-depth-series-brief --series-id … --out …` 실행 완료 시 증거 체인 완료 |
| 증거 상세 | `docs/phase22_evidence.md` |

**다음 담당자:** 활성 시리즈는 `close` 후 재사용하지 않는다. 새 슬롯이 필요하면 `advance-public-repair-series` 또는 `advance-public-depth-iteration`으로 연 뒤 다시 `active_series_id`를 확인한다.

## 실측 브랜치·분포 (코드베이스)

- **단위/픽스처**: `improvement_classification` 네 갈래 전부 `test_phase22_public_depth_iteration`에서 검증; `persisted_escalation_branch_counts`·`improvement_classification_counts`는 운영 시리즈에 대해 **`export-public-depth-series-brief`** JSON으로 집계(저장소 CI에는 실 DB 없음).
- **Phase 23 권고**: 에스컬레이션이 `continue_public_depth` / `hold_and_repeat_public_repair`인 동안은 **공개 깊이·수리 반복 증거 축적(Phase 23 동일 궤도)** 을 우선. **`open_targeted_premium_discovery`** 및 브리프 v2 게이트가 성립할 때만 **타깃 프리미엄 디스커버리 검토 준비**(라이브 통합 아님). `public_depth_near_plateau_review_required`는 운영자 **플래토 리뷰** 트리거.

## 마이그레이션 (누적)

- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql` — 적용 후 `smoke-phase22-public-depth-iteration`.

## 패치 보고·증거

- `docs/phase22_patch_report.md`
- `docs/phase22_evidence.md` — 클로징 체크리스트, pytest·브리프 재현, 핸드오프 질문표

## 패치마다 동일한 운영 순서 (고정)

- **권장(Phase 23+)**: `docs/OPERATOR_POST_PATCH.md` 상단 — `run-post-patch-closeout`
- **스모크 일괄(레거시/부록)**: `./scripts/operator_post_patch_smokes.sh` (phase17→22)

---

# HANDOFF — Phase 21 (Iteration governance, selectors, infra quarantine)

## 현재 제품 위치

- **Phase 11–20**: 이전과 동일하되, Phase 21에서 **선택자 완성**(`latest-success`, `latest-compatible`, `latest-for-program`, `from-latest-pair` → `resolve-repair-campaign-pair`, `latest-active-series`), **시리즈 라이프사이클**(pause / resume / close + `governance_audit_json`), **플래토 기본값에서 인프라 실패 런 격리**(`included_run_count`, `excluded_infra_failure_count`), **`advance-public-repair-series` 단일 골든 패스**, **에스컬레이션 브리프 v2**(포함/제외 런, 호환 근거, 트렌드 델타, 카운터팩추얼, 프리미엄 게이트 체크리스트)가 추가됨.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 출력을 참조하지 않음(`state_change.runner` 검증 테스트 유지). 프리미엄 **라이브** 통합 자동 오픈 없음.

## Phase 21로 가능해진 것

1. **`smoke-phase21-iteration-governance`**, **`pause-public-repair-series`**, **`resume-public-repair-series`**, **`close-public-repair-series`**
2. **`advance-public-repair-series`** — 호환 활성 시리즈 → (캠페인 1회 또는 attach) → 멤버 append(동일 `repair_campaign_run_id` 멱등) → 플래토/에스컬레이션 → 브리프 JSON+MD + 요약 한 줄
3. **`resolve-repair-campaign-pair`**, Phase 19/20 보고용 **`--repair-campaign-id`** 확장 선택자
4. **`report-public-repair-plateau --include-infra-failed-runs`** (기본은 인프라 격리 유지)
5. Transient REST 오류에 대한 **리스트 조회 재시도**(resolver 경로) 및 캠페인 실패 시 **`rationale_json.failure_audit`**

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase21_iteration_governance.py -q` — **10 passed**
- 전체 테스트 개수는 상단 **Phase 22** 절 참고.

## 검증·운영 스냅샷 (2026-04-07, 운영 DB + 로컬 CLI)

| 항목 | 결과 |
|------|------|
| `20250424100000_phase21_iteration_governance.sql` | 운영자 적용 완료 |
| `smoke-phase21-iteration-governance` | 통과(이전 스텝과 일관) |
| `advance-public-repair-series` (골든 패스) | 실행 완료; 활성 시리즈·멤버·플래토/에스컬레이션·브리프 흐름 확인 |
| **시리즈 라이프사이클** (`--series-id` = 해당 시리즈의 `public_repair_iteration_series.id`, 예: `advance`/`list-public-repair-series` 출력) | `pause-public-repair-series` → `{"ok": true, "status": "paused"}` → `resume-public-repair-series` → `active` → `close-public-repair-series` → `closed` (REST 200) |
| 원격 저장소 | `git push origin main` 완료 — **28026fb** (`main`), 구현 베이스 **3d956e9** |

**참고:** 한 시리즈를 `close`하면 동일 `(program_id, universe_name, policy_version)`에 대해 새 **active/paused** 슬롯이 비므로, 다음 반복은 `advance-public-repair-series` 또는 `get_or_create_iteration_series` 경로로 **새 시리즈**가 잡힌다.

## 마이그레이션 (누적)

- **Phase 21**: `20250424100000_phase21_iteration_governance.sql` — 운영 DB에 적용 후 `smoke-phase21-iteration-governance` 권장.
- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql`

## 패치 보고·증거

- `docs/phase21_patch_report.md`

## Phase 23 방향 제안 (Phase 22 이후)

- 공개 우선 증거가 쌓이는 동안 **`advance-public-depth-iteration`** / **`advance-public-repair-series`**를 교대로 쓰며 `export-public-depth-series-brief`로 분포를 고정.
- 에스컬레이션·게이트가 **`open_targeted_premium_discovery`**로 수렴할 때만 Phase 24급 **프리미엄 디스커버리 설계**(라이브 아님) 검토.

## Git

- **구현 커밋** **3d956e9ece1fbd5ecc9722dc16d3acc83c853a7f** (`3d956e9`) — `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`.
- **문서·HANDOFF 정리** **28026fb** — `docs: Phase 21 README, HANDOFF commit SHA, patch report MCP note` (원격 `origin/main`에 푸시됨, 2026-04-07 확인).
- 이후 로컬만 앞서 있는 경우: `git log -1 --oneline` 로 HEAD 확인.

---

# HANDOFF — Phase 20 (Public Repair Iteration Manager & Escalation Gate)

## 현재 제품 위치

- **Phase 11–19**: 이전과 동일(공개 기판·타깃 빌드아웃·수리 캠페인 폐쇄 루프 등).
- **Phase 20 (본 패치)**: 동일 프로그램에 대해 **반복된 Phase 19 런**을 `public_repair_iteration_series` / `public_repair_iteration_members`로 묶고, `trend_snapshot_json`을 쌓아 **플래토·에스컬레이션**을 결정한다. 권고는 **`continue_public_depth`** \| **`hold_and_repeat_public_repair`** \| **`open_targeted_premium_discovery`**(프리미엄 **발견** 궤도만 열지, 라이브 통합 아님). **골든 패스**: `--program-id latest`(+필요 시 `--universe`)·`--repair-campaign-id latest`로 UUID 수동 추적 최소화. **프로덕션 스코어 경로는 `public_repair_iteration` 미참조**.

## Phase 20로 가능해진 것

1. **`run-public-repair-iteration`**: Phase 19 캠페인 1회 실행 후 시리즈에 멤버 추가 + `public_repair_escalation_decisions` 적재.
2. **`report-public-repair-iteration-history`**: `--series-id` 또는 `--program-id`(latest 가능).
3. **`report-public-repair-plateau` / `export-public-repair-escalation-brief`**: 활성 시리즈 기준 재계산·브리프.
4. **`list-public-repair-series`**, **`report-latest-repair-state`**, **`report-premium-discovery-readiness`**.
5. Phase 19 **`report-public-repair-campaign` / `compare-*` / `export-public-repair-decision-brief` / `list-repair-campaigns` / `run-public-repair-campaign`**: `latest` 선택자 및 `--universe` 지원.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase20.py` — **11 passed**
- 전체 테스트 개수는 상단 **Phase 21** 절 참고 (Phase 20 단독 카운트는 위 명령 기준).

## 검증·운영 스냅샷 (2026-04-07, `sp500_current`, `--program-id latest`)

| 항목 | 결과 |
|------|------|
| `smoke-phase20-repair-iteration` | `db_phase20_repair_iteration: ok` |
| `report-public-repair-iteration-history` | `ok: true`; 시리즈·멤버(seq 1)·에스컬레이션 행 |
| `report-public-repair-plateau` | `ok: true`; `hold_and_repeat_public_repair`, 근거 `insufficient_iterations` |
| `export-public-repair-escalation-brief` → `docs/public_repair/escalation_latest.json` | `ok: true`, 동명 `.md` |
| `report-premium-discovery-readiness` | `premium_discovery_ready: false` |
| `report-latest-repair-state` / `list-public-repair-series` | `ok: true` |
| `list-repair-campaigns` | `ok: true`; 과거 1건은 REST **502**로 `failed` 기록 가능(일시 인프라) |
| `report-public-repair-campaign --repair-campaign-id latest` | `ok: true`; 스텝·비교·`repair_insufficient_repeat_buildout` 일관 |
| 후속 (Phase 21, 동일 시리즈 UUID 기준) | `pause` → `resume` → `close` 라이프사이클 CLI REST 200·`ok: true`; 시리즈는 **closed** — 상세·SHA·테스트 카운트는 **상단 Phase 21** 스냅샷 |

상세: `docs/phase20_completion_report.md` · 증거: `docs/phase20_evidence.md`.

## 마이그레이션 (누적)

- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`
- **Phase 21**: `20250424100000_phase21_iteration_governance.sql`
- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql`

---

# HANDOFF — Phase 19 (Public Repair Campaign & Revalidation Loop)

## 현재 제품 위치

- **Phase 11–18**: 이전과 동일(공개 기판 진단·타깃 빌드아웃·재검증 트리거 불리언 등).
- **Phase 19 (본 패치)**: **수리 → (게이트 충족 시) Phase 15/16 재실행 → 전후 연구 결과 비교 → 단일 최종 분기**를 한 번에 감사 가능한 행으로 남긴다. `run-public-repair-campaign`은 베이스라인 커버리지·제외 액션 스냅샷·최신 캠페인 권고를 고정한 뒤 `run-targeted-public-buildout`을 호출하고, `report-revalidation-trigger`와 동일한 **양쪽 불리언**이 모두 true일 때만 `run_validation_campaign(..., force_rerun)`을 수행한다. **프로덕션 스코어 경로는 `public_repair_campaign` 미참조**(`state_change.runner`에 해당 문자열 없음).

## Phase 19로 “증명” 가능해진 것

- 한 캠페인 런에 대해 **무엇을 시도했는지**, **기판이 개선됐는지**, **재실행이 실제로 돌았는지**, **생존 분포·캠페인 권고가 어떻게 바뀌었는지**, **다음 분기(`continue_public_depth` \| `consider_targeted_premium_seam` \| `repair_insufficient_repeat_buildout`)**가 무엇인지 DB·CLI로 재현한다.
- **`consider_targeted_premium_seam` 분기는 재실행 증거 없이는 나오지 않는다**(정책 코드 불변식).

## 검증·테스트 결과 (2026-04-06 기준)

| 항목 | 결과 |
|------|------|
| Supabase 마이그레이션 `20250422100000_phase19_public_repair_campaign.sql` | 적용 완료(운영자 확인) |
| `smoke-phase19-public-repair-campaign` | 네 테이블 REST 조회 200, `db_phase19_public_repair_campaign: ok` |
| `pytest src/tests/test_phase19.py -q` | **14 passed** |
| `pytest src/tests -q` (전체) | **242 passed** (외부 `edgar` DeprecationWarning만) |
| `export-public-repair-decision-brief --out docs/public_repair/briefs/latest.json` | `ok: true`, 동명 `.md` 생성(실캠페인 런 ID는 실행마다 상이) |

상세 체크리스트·클로징 순서: `docs/phase19_completion_report.md` · 증거 메모: `docs/phase19_evidence.md`.

## 운영 후 HANDOFF에 채울 항목 (실행 증거 기준)

| 질문 | 어디서 확인 |
|------|-------------|
| 수리 후 기판이 실질적으로 나아졌는가? | `public_repair_campaign_runs.improvement_report_id` → `public_buildout_improvement_reports` 또는 전후 `baseline_coverage_report_id` / `after_coverage_report_id` |
| Phase 15/16 재실행이 실제로 있었는가? | `reran_phase15`, `reran_phase16`, `after_campaign_run_id`; `rerun_skip_reason_json`이 비어 있지 않으면 스킵 이유 |
| 레시피 생존·캠페인 권고가 개선됐는가? | `public_repair_revalidation_comparisons` |
| 다음이 공개 깊이 우선인가, 프리미엄 seam 검토인가, 추가 빌드아웃인가? | `final_decision` + `public_repair_campaign_decisions.rationale_json` |

## 마이그레이션 (누적)

- **Phase 19**: `20250422100000_phase19_public_repair_campaign.sql`
- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`

---

# HANDOFF — Phase 18 (Targeted Public Build-Out)

## 현재 제품 위치

- **Phase 11–17**: 이전과 동일(연구 엔진·캠페인·공개 기판 깊이 확장·커버리지/uplift).
- **Phase 18 (본 패치)**: **제외 사유 기반 타깃 수리** — 우세 제외 키에 맞춰 상한 있는 빌드(검증 패널·선행수익·factor 패널·state change)를 오케스트레이션하고, `public_buildout_*`·`public_exclusion_action_reports`에 감사 흔적을 남긴다. **제품 스코어 경로는 `public_buildout` 미참조**(`state_change.runner` 소스에 해당 문자열 없음; 빌드 경로에서만 `run_state_change` 호출).

## Phase 18으로 가능해진 것

1. **`report-public-exclusion-actions`**: 제외 분포·심볼 큐·권장 액션 JSON(`--persist`).
2. **`run-targeted-public-buildout`**: 플래그·상한으로 타깃 제외만 공격; `dry_run` 시 DB 작업 최소화.
3. **`report-buildout-improvement`**: 두 커버리지 리포트 UUID로 제외·기판 델타; `--persist` 시 `public_buildout_run_id` 없이도 개선 행 저장 가능.
4. **`report-revalidation-trigger`**: 프로그램 유니버스 기준 **명시적** `recommend_rerun_phase15` / `recommend_rerun_phase16`.
5. **`export-buildout-brief`**: JSON+Markdown 브리프.

## 다음 단계 권고 (증거 기준)

1. `20250421100000_phase18_public_buildout.sql` 적용 후 `smoke-phase18-public-buildout`.
2. `report-public-depth-coverage`로 기준선 → 필요 시 Phase 17 확장 또는 Phase 18 **타깃** 빌드.
3. 전후 커버리지로 `report-buildout-improvement` 또는 오케스트레이션 결과의 `improvement_summary_json` 확인.
4. 기판이 임계를 넘으면 `report-revalidation-trigger`의 불리언을 보고 Phase 15/16 재실행을 **수동** 검토(자동 연결 없음).

## 마이그레이션 (누적)

- **Phase 18**: `20250421100000_phase18_public_buildout.sql`
- **Phase 19**: `20250422100000_phase19_public_repair_campaign.sql`
- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`

---

## Phase 17 요약

### Phase 17으로 가능해진 것

1. **`report-public-depth-coverage`**: 최신 멤버십 as_of 기준 조인 행 수·품질 쉐어·제외 분포 JSON.
2. **`run-public-depth-expansion`**: before/after 커버리지 + uplift 행 생성(플래그로 빌드 단계 제어).
3. **`report-quality-uplift`**: 두 커버리지 리포트 UUID로 델타 계산(옵션 DB 저장).
4. **`report-research-readiness`**: 프로그램의 `universe_name`으로 기판 스냅샷을 보고 **Phase 15/16 재실행 권고 불리언**(휴리스틱 임계: `MIN_SAMPLE_ROWS * 5` joined 행 + `thin_input_share` 완화).
5. **`export-public-depth-brief`**: JSON+Markdown 아티팩트(`--universe` 또는 `--program-id`).

## `thin_input`이 “실제로” 줄었는지

- **코드가 자동으로 단정하지 않는다.** 확장 전후 `public_depth_coverage_reports.metrics_json`의 `thin_input_share` 및 `joined_recipe_substrate_row_count`를 비교해 운영자가 판단한다. `public_core_cycle_quality_runs`는 **해당 유니버스** 최근 N건으로 쉐어를 추정한다.

## 다음 단계 권고 (증거 기준)

1. Supabase에 `20250420100000_phase17_public_depth.sql` 적용 후 `smoke-phase17-public-depth`.
2. 대상 유니버스로 `report-public-depth-coverage` → 기준선 저장(`--persist` 또는 확장 러의 before).
3. 필요 시 `run-public-depth-expansion --run-validation-panels` 등으로 **상한 있는** 공개 빌드 실행 → after·uplift 확인.
4. **`joined_recipe_substrate_row_count`가 눈에 띄게 증가**하고 **thin_input 쉐어가 완화**되면: **Phase 15/16 재실행**을 우선 검토.
5. 그렇지 않으면: **공개 기판 추가 확장**(유니버스 전용 factor/패널 빌드 설계 등)을 이어가고, 캠페인이 `targeted_premium_seam_first`로 바뀐 **별도 증거**가 있을 때만 프리미엄 seam을 헤드라인으로 올린다.

### Phase 17 마이그레이션

- `20250420100000_phase17_public_depth.sql`

---

## Phase 16 이전 요약

- `docs/phase16_evidence.md`, Phase 15 이하 문서 참고.
