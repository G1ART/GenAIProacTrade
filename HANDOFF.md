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

- `pytest src/tests/test_phase21_iteration_governance.py` — **11 passed**
- `pytest src/tests -q` — **263 passed** (외부 `edgar` DeprecationWarning만)

## 마이그레이션 (누적)

- **Phase 21**: `20250424100000_phase21_iteration_governance.sql` — 운영 DB에 적용 후 `smoke-phase21-iteration-governance` 권장.

## 패치 보고·증거

- `docs/phase21_patch_report.md`

## Phase 22 방향 제안

- 에스컬레이션이 **`continue_public_depth` / `hold_and_repeat_public_repair`**인 프로그램이 많으면 → **공개 깊이 반복(Phase 22 = public-depth iteration)** 을 우선.
- **`open_targeted_premium_discovery`**가 반복되고 게이트 체크리스트가 충족되면 → **타깃 프리미엄 발견 프로그램 오프너**(라이브 통합이 아닌 발견/설계 궤도)를 Phase 22 후보로 둠.

## Git

- **구현 커밋** **3d956e9ece1fbd5ecc9722dc16d3acc83c853a7f** (`3d956e9`) — `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`.
- **문서 정리**(README·HANDOFF SHA·patch report): `git log -1 --oneline` 로 확인 (메시지 `docs: Phase 21 README, HANDOFF commit SHA, patch report MCP note`).

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

상세: `docs/phase20_completion_report.md` · 증거: `docs/phase20_evidence.md`.

## 마이그레이션 (누적)

- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`
- **Phase 21**: `20250424100000_phase21_iteration_governance.sql`

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
