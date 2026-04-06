# Phase 16 증거 메모 — Validation Campaign Orchestrator

## 목적

Phase 15는 **가설 단위** 검증이다. Phase 16은 동일 프로그램에서 **자격·호환되는 검증을 묶어** 생존/실패/프리미엄 힌트를 집계하고, **하나의 기계-readable 전략 권고**로 요약한다.

## 스키마

| 객체 | 설명 |
|------|------|
| `validation_campaign_runs` | `program_id`, `policy_version`, `run_mode`, `hypothesis_selection_json`, `aggregate_metrics_json`, `recommendation`, `rationale_json` |
| `validation_campaign_members` | 가설별 `validation_run_id`, `survival_status`, 베이스라인/취약성/프리미엄 요약 JSON |
| `validation_campaign_decisions` | 권고·근거·임계값·반증 시 행동 JSON |
| `recipe_validation_runs.join_policy_version` | 캠페인 **재사용 호환**용(예: `cik_asof_v1`). 마이그레이션에서 기존 `completed` 행 백필. |

## 호환 재사용 규칙

동일 가설에 대해 최근 `completed` 실행이 아래와 일치할 때만 재사용:

- `join_policy_version == cik_asof_v1`
- `baseline_config_json`·`window_config_json.stability_metric`·`cohort_config_json.dimensions` 및 `program_quality_class`가 **현재** 프로그램 맥락과 동일
- `cohort_config_json.config_version`이 없거나 `1`

불일치 시 `reuse_or_run`은 `run-recipe-validation`과 동일 경로로 재실행한다.

## 권고 enum

- `public_data_depth_first` — thin_input·degraded 실패 비중 또는 프로그램 품질 맥락이 공개 기판 부족을 가리킬 때
- `targeted_premium_seam_first` — strong/usable 맥락에서 잔차 모순·프리미엄 힌트 실패가 집중될 때
- `insufficient_evidence_repeat_campaign` — 자격 가설·완료 검증 수가 임계 미만일 때

정책 구현: `src/validation_campaign/decision_gate.py`.

## CLI (재현)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase16-validation-campaign
python3 src/main.py list-eligible-validation-hypotheses --program-id <PROGRAM_UUID>
python3 src/main.py run-validation-campaign --program-id <PROGRAM_UUID> --run-mode reuse_or_run
python3 src/main.py report-validation-campaign --campaign-run-id <CAMPAIGN_UUID>
python3 src/main.py report-program-survival-distribution --program-id <PROGRAM_UUID>
python3 src/main.py export-validation-decision-brief --campaign-run-id <CAMPAIGN_UUID> --out docs/validation_campaign/briefs/latest.json
```

## 거버넌스

- `state_change.runner`·제품 스코어는 `validation_campaign`을 **참조하지 않음** (`promotion_rules.assert_no_auto_promotion_wiring`).

## 테스트

`src/tests/test_phase16.py` — 자격, 호환, 집계 라우팅, enum, 브리프, runner 비참조.
