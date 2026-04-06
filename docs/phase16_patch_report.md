# Phase 16 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase16_Workorder_2026-04-06_revised.md`

## HEAD (커밋 체인)

| 구분 | 값 |
|------|-----|
| 패치 직전 | `20c7909` — Phase 15 조인(CIK·`as_of≤signal`) 수정 팁 |
| 기능 머지 | `8540a5c` — `feat(phase16): validation campaign orchestrator, decision gate, CLI` |
| 문서 후속 | `4469190` … `b696888` — 패치 리포트·tip 문구 정리 (작은 docs 커밋 연쇄) |
| **저장소 팁 (코드·초기 문서)** | `b696888` |
| **운영 증거 포함 정식 패치 리포트** | `7dbdd9b` |

## 변경 요약

Phase 15의 **가설 단위** 검증을 **프로그램 단위 캠페인**으로 묶는다. 자격(`candidate_recipe`/`sandboxed`·리뷰·심판·비아카이브 프로그램)을 통과한 가설에 대해, **`join_policy_version`·베이스라인·코호트·창 설정**이 현재 정책과 일치하는 `completed` 실행은 **재사용**하고, 아니면 `run-recipe-validation`으로 **재실행**한다. 멤버별 생존·베이스라인 열세·실패 사유·프리미엄 힌트를 집계한 뒤 **결정 게이트**가 정확히 하나의 권고만 낸다: `public_data_depth_first` \| `targeted_premium_seam_first` \| `insufficient_evidence_repeat_campaign`. `state_change.runner` 등 제품 스코어 경로는 `validation_campaign`을 **참조하지 않는다**.

### 산출물 (파일·경로)

- **마이그레이션**: `supabase/migrations/20250419100000_phase16_validation_campaign.sql` — `validation_campaign_runs` / `validation_campaign_members` / `validation_campaign_decisions`, `recipe_validation_runs.join_policy_version` + 기존 `completed` 백필 `cik_asof_v1`
- **패키지**: `src/validation_campaign/` (`constants`, `compatibility`, `decision_gate`, `service`, `__init__.py`)
- **Phase 15 정렬**: `src/research_validation/constants.py`, `src/research_validation/service.py` — `JOIN_POLICY_VERSION`, `COHORT_CONFIG_VERSION`, `WINDOW_STABILITY_METRIC_KEY`, 실행 행에 `join_policy_version` 컬럼·`quality_filter_json` 동기화
- **DB**: `src/db/records.py` — Phase 16 CRUD·`smoke_phase16_validation_campaign_tables`
- **CLI**: `src/main.py` — 스모크·자격 목록·캠페인 실행·리포트·프로그램 생존 분포·브리프 export
- **거버넌스**: `src/research_registry/promotion_rules.py` — runner 소스·문서에 `validation_campaign` 경계 명시
- **테스트**: `src/tests/test_phase16.py`
- **문서**: `docs/phase16_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`, 본 파일

### 설계 메모 (워크오더 대응)

- **호환 재사용**: Post-fix Phase 15 조인을 `join_policy_version == cik_asof_v1` 및 `baseline`/`cohort`/`window` JSON 동등성으로 고정; `cohort_config.config_version` 없음(`null`)은 레거시 호환으로 허용.
- **권고**: thin_input·실패 사유 비중·strong/usable 맥락·잔차/프리미엄 실패 집중도 등은 `decision_gate.py`에 명시.

## 새 CLI

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase16-validation-campaign` | `validation_campaign_*` 테이블 도달 |
| `list-eligible-validation-hypotheses --program-id` | 캠페인 자격 가설 |
| `run-validation-campaign --program-id [--run-mode …]` | 캠페인 실행·DB 적재 |
| `report-validation-campaign --campaign-run-id` | 캠페인 JSON |
| `report-program-survival-distribution --program-id` | 프로그램 가설별 최근 완료 검증 생존 |
| `export-validation-decision-brief --campaign-run-id --out` | 권고 브리프 JSON+Markdown |

`--program-id`에는 **`research_programs.id`**만 사용한다. 가설 UUID를 넣으면 `program_not_found`가 난다.

## 테스트

```bash
cd src
python3 -m pytest tests/test_phase16.py tests/ -q
```

**결과**: 전체 **212 passed** (Phase 16 반영·로컬 재실행 기준, 2026-04-06).

## 운영 증거 (실 Supabase·로컬 CLI, 2026-04-06)

다음은 사용자 환경에서 수행된 로그를 요약한 것이다. HTTP는 **200/201**, 캠페인 POST는 **201 Created**.

### `list-eligible-validation-hypotheses`

| 항목 | 값 |
|------|-----|
| `program_id` | `45ec4d1a-fd77-4254-9390-462da04d1d11` |
| `n_eligible` | 3 |
| 자격 가설 | `8ffeefc1-…bcb7`, `eaba687b-…0e7f`, `aad2f805-…b948` (상태 `sandboxed`) |

### `run-validation-campaign --run-mode reuse_or_run`

| 항목 | 값 |
|------|-----|
| `campaign_run_id` | `f9106163-da85-416e-950b-c32d7be8911e` |
| `recommendation` | `public_data_depth_first` |
| `n_eligible` / `n_validated` | 3 / 3 |
| `skipped` | `[]` |
| `hypotheses_reran` | `[]` → 세 가설 모두 **기존 completed 검증 호환 재사용** (신규 `run-recipe-validation` 없음) |

**집계 요약** (`aggregate_metrics_json`에 상응): `survives` 0, `weak_survival` 3, `baseline_loss_distribution.state_change_score_only` 3, `failure_reason_counts.thin_input_program_context_dependence` 3, `n_contradictory_failure_cases` 0, `dominant_program_quality_class` `thin_input`. 권고는 워크오더가 예상한 **공개 기판 부족 우선** 경로와 정합.

### `export-validation-decision-brief`

- `--campaign-run-id f9106163-da85-416e-950b-c32d7be8911e`
- 출력: `docs/validation_campaign/briefs/latest.json`, `docs/validation_campaign/briefs/latest.md`

### 전체 회귀

- `cd src && python3 -m pytest tests/ -q` → **212 passed** (edgar DeprecationWarning 3건만, 실패 없음)

## 재현 CLI (요약)

```bash
cd /Users/hyunminkim/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py smoke-phase16-validation-campaign
python3 src/main.py list-eligible-validation-hypotheses --program-id 45ec4d1a-fd77-4254-9390-462da04d1d11
python3 src/main.py run-validation-campaign --program-id 45ec4d1a-fd77-4254-9390-462da04d1d11 --run-mode reuse_or_run
python3 src/main.py export-validation-decision-brief --campaign-run-id <위_JSON의_campaign_run_id> --out docs/validation_campaign/briefs/latest.json
```

마지막 줄의 `campaign_run_id`는 **매 실행마다 새 UUID**이므로, `run-validation-campaign` 출력의 값을 그대로 복사한다. Supabase에 **Phase 16 마이그레이션**이 선적용되어 있어야 한다.

## 결론

- Phase 16 **스키마·코드·테스트·문서**는 `8540a5c` 기준으로 반영되었고, 문서용 소커밋이 `b696888`까지 이어진다.
- 실 DB·CLI 기준으로 **잠금 프로그램 한 건**에 대해 캠페인이 **자격 3·검증 3·전량 재사용**으로 완료되었고, 권고는 **`public_data_depth_first`**이며 집계 증거와 일치한다.
- Phase 15 단일 검증 증거(동일 세 가설 `weak_survival` 등)는 `docs/phase15_patch_report.md`에 정리되어 있으며, Phase 16은 그 결과를 **캠페인 단일 권고**로 승격한 층이다.
