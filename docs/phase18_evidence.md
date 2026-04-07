# Phase 18 증거 메모 — Targeted Public Substrate Build-Out

## 목적

Phase 17에서 측정한 **제외 사유·심볼 큐**를 바탕으로, **사유별 상한 있는 수리**(factor/검증 패널·선행수익·state change)를 오케스트레이션하고, **before/after 개선**과 **Phase 15/16 재실행 권고 불리언**을 DB·CLI로 남긴다. `state_change.runner`는 `public_buildout`을 **참조하지 않는다**(Phase 18 빌드 경로에서만 `run_state_change`를 호출).

## 스키마

| 객체 | 설명 |
|------|------|
| `public_exclusion_action_reports` | 커버리지 스냅샷 기준 제외 분포·액션 큐 JSON |
| `public_buildout_runs` | 타깃 제외 키·시도한 작업·요약·상태 |
| `public_buildout_improvement_reports` | 전후 메트릭·제외 분포·`improvement_summary_json`; `public_buildout_run_id` nullable(CLI만 개선 저장 가능) |

## 추적 제외 키

`no_validation_panel_for_symbol`, `no_state_change_join`, `missing_excess_return_1q` — `TRACKED_EXCLUSION_KEYS`와 액션 매핑은 `src/public_buildout/constants.py`.

## 재검증 트리거

`report-revalidation-trigger`는 `research_programs`의 `universe_name`으로 기판 스냅샷을 읽고, `joined_recipe_substrate_row_count`·`thin_input_share`에 대해 **별도** `recommend_rerun_phase15` / `recommend_rerun_phase16`을 계산한다(임계: `MIN_SAMPLE_ROWS` 배수 및 Phase 15/16별 thin 상한).

## CLI (재현)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase18-public-buildout
python3 src/main.py report-public-exclusion-actions --universe sp500_current
python3 src/main.py run-targeted-public-buildout --universe sp500_current --dry-run
python3 src/main.py report-buildout-improvement --before-report-id <UUID> --after-report-id <UUID>
python3 src/main.py report-revalidation-trigger --program-id PASTE_PROGRAM_UUID_HERE
python3 src/main.py export-buildout-brief --universe sp500_current --out docs/public_depth/briefs/buildout_latest.json
```

마이그레이션: `supabase/migrations/20250421100000_phase18_public_buildout.sql`.
