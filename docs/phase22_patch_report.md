# Phase 22 — Public-depth iteration under repair series governance

**Date:** 2026-04-07  
**Evidence / closure memo:** `docs/phase22_evidence.md` (시리즈 브리프·pytest 클로징, 2026-04-01 기준)

## Closure checklist (시리즈 브리프 + 테스트 완료 시)

| 단계 | 명령 / 산출 | 기대 |
|------|-------------|------|
| DB | `20250425100000_phase22_public_depth_iteration.sql` 적용 후 | `smoke-phase22-public-depth-iteration` 통과 |
| 활성 시리즈 | `report-latest-repair-state … --active-series-id-only` | UUID 한 줄 |
| 브리프 | `export-public-depth-series-brief --series-id … --out …` | JSON(+MD 경로) |
| 회귀 | `PYTHONPATH=src pytest src/tests -q` | **278 passed** (외부 `edgar` DeprecationWarning만) |

## Migration

Apply `supabase/migrations/20250425100000_phase22_public_depth_iteration.sql`:

- `public_repair_iteration_members.member_kind` (`repair_campaign` | `public_depth`)
- Nullable `repair_campaign_run_id`; optional `public_depth_run_id` → `public_depth_runs`
- Partial unique indexes on non-null FKs; XOR check (exactly one of repair vs depth)

Smoke: `python3 src/main.py smoke-phase22-public-depth-iteration`

패치 공통 절차(스모크 일괄·활성 시리즈 확인): `docs/OPERATOR_POST_PATCH.md` · `./scripts/operator_post_patch_smokes.sh`

## Commands

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase22-public-depth-iteration
python3 src/main.py advance-public-depth-iteration --program-id latest --universe YOUR_UNIVERSE \
  --out docs/public_depth/advance_depth_latest
python3 src/main.py export-public-depth-series-brief --series-id SERIES_UUID \
  --out docs/public_depth/series_brief_latest
```

- **`advance-public-depth-iteration`**: 활성(또는 없으면 생성) 시리즈 → `build_research_readiness_summary` + `build_revalidation_trigger`(전) → `run_public_depth_expansion` → (후) readiness/trigger → `phase22_ledger` + 멤버 append → 플래토/에스컬레이션 → `public_depth_operator_signal` + depth brief + repair escalation brief(JSON/MD). Phase 15/16 캠페인은 **`--execute-phase15-16-revalidation`** 일 때만, **게이트가 이전 대비 새로 열린 경우**에만 실행.
- **`export-public-depth-series-brief`**: 시리즈 전체 멤버·포함/제외 런·개선 분류 분포·저장된 에스컬레이션 브랜치 카운트·현재 권고·depth 신호·최신 제외 키.

## Trend ledger (`phase22_ledger` in `trend_snapshot_json`)

- `thin_input_share_*`, `joined_recipe_substrate_row_count_*` (before/after/delta)
- `dominant_exclusion_keys_before` / `_after`
- `research_readiness_before` / `_after` (`recommend_rerun_phase_15_16`)
- `rerun_gate_before` / `_after` (phase15/16 booleans)
- `buildout_actions_attempted` / `buildout_actions_succeeded` (코어 before/after 커버리지 + optional ops)
- `improvement_classification`: `meaningful_progress` | `marginal_progress` | `no_material_progress` | `degraded_or_noisy` (`marginal_policy.py` 임계값은 Phase 20 상수와 정렬)

## Operator signal (not premium gate)

`compute_public_depth_operator_signal`: `continue_public_depth_buildout` | `repeat_targeted_public_repair` | `public_depth_near_plateau_review_required` (`depth_signal.py`).

## Plateau / infra quarantine

`collect_plateau_snapshots_for_series`는 `public_depth` 멤버에 대해 `public_depth_runs` 행을 조회해 실패·인프라 패턴을 Phase 21과 동일 정책으로 제외한다.

## Before/after trend (실제 시리즈)

운영 DB에 마이그레이션 적용 후 `advance-public-depth-iteration` 1회 이상 실행한 시리즈에 대해 `--out` JSON의 `ledger`·`depth_series_brief`에 before/after/delta가 기록된다. (이 저장소 CI에는 실 DB 없음 — 로컬 증거는 픽스처 테스트.)

## Tests

- `src/tests/test_phase22_public_depth_iteration.py` — 분류 4종, 플래토 제외, 멱등, 브리프 형태, runner/프로모션 경계, CLI 등록
- 전체: `pytest src/tests -q` — **278 passed**

## Production scoring boundary

`state_change.runner`에 `public_repair_iteration` / `public_repair_campaign` 문자열 미포함 — `test_phase22_public_depth_iteration.test_runner_still_no_public_repair_iteration_reference`

## Phase 23 권고 (정책)

- **계속 공개 깊이 반복(Phase 23 = 동일 궤도 심화)**: 에스컬레이션이 `continue_public_depth` 또는 `hold_and_repeat_public_repair`이고, `public_depth_operator_signal`이 `continue_public_depth_buildout` 또는 `repeat_targeted_public_repair`인 동안. 실제 분포는 운영에서 `export-public-depth-series-brief`의 `persisted_escalation_branch_counts`·`improvement_classification_counts`로 집계.
- **타깃 프리미엄 디스커버리 검토 준비**: 기존 Phase 20/21 에스컬레이션이 이미 `open_targeted_premium_discovery`이고 브리프 v2 프리미엄 게이트 체크리스트가 성립할 때만(자동 오픈 없음). `public_depth_near_plateau_review_required`는 **운영자 플래토 리뷰**용이지 프리미엄 라이브 통합이 아님.
