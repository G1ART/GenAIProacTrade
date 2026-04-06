# Phase 17 증거 메모 — Public Substrate Depth Expansion & Quality Lift

## 목적

Phase 16이 `public_data_depth_first`를 권고한 뒤, **공개 데이터 기판이 실제로 두꺼워졌는지**를 유니버스·프로그램 단위로 **수치·제외 사유**로 남긴다. 레시피 검증·캠페인은 이 단계에서 **자동으로 돌지 않으며**, 스코어 경로와 분리된다.

## 스키마

| 객체 | 설명 |
|------|------|
| `public_depth_runs` | 확장 실행 메타: `universe_name`, `policy_version`, `status`, `expansion_summary_json` |
| `public_depth_coverage_reports` | `metrics_json`(조인 행 수·품질 쉐어·발행자 카운트 등), `exclusion_distribution_json`, `snapshot_label` ∈ before \| after \| standalone |
| `public_depth_uplift_reports` | 두 커버리지 리포트 ID와 `uplift_metrics_json`(델타·thin_input 개선 여부) |

## 커버리지 지표(요약)

- `public_core_cycle_quality_runs` 최근 N건(유니버스 필터)으로 **thin_input / degraded / strong / usable_with_gaps** 비율.
- `factor_market_validation_panels` × 최신 완료 `issuer_state_change_scores` run: **PIT 조인**(`pick_state_change_at_or_before_signal`)으로 `joined_recipe_substrate_row_count`.
- 제외 사유: `missing_excess_return_1q`, `no_state_change_join`, `no_validation_panel_for_symbol` 등 — `dominant_exclusion_reasons`에 결정적 정렬.

## 확장 러너

`run-public-depth-expansion`은 **before → (선택) 전역 상한 빌드 → after → uplift 적재** 순서다. `--run-validation-panels` / `--run-forward-returns`는 기존 `run_validation_panel_build` / `run_forward_returns_build`의 **전역 `limit_panels`**를 재사용한다. `--max-universe-factor-builds`로 유니버스 티커→CIK에 한해 factor 패널 빌드를 **상한**만큼만 호출할 수 있다.

## CLI (재현)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase17-public-depth
python3 src/main.py report-public-depth-coverage --universe <UNIVERSE_NAME>
python3 src/main.py run-public-depth-expansion --universe <UNIVERSE_NAME>
python3 src/main.py report-quality-uplift --before-report-id <UUID> --after-report-id <UUID>
python3 src/main.py report-research-readiness --program-id <PROGRAM_UUID>
python3 src/main.py export-public-depth-brief --universe <UNIVERSE_NAME> --out docs/public_depth/briefs/latest.json
```

## 거버넌스

- `state_change.runner`는 `public_depth`를 **참조하지 않음** (`promotion_rules.assert_no_auto_promotion_wiring`).

## 테스트

`src/tests/test_phase17.py` — 커버리지 키, 업리프트, 제외 순위, readiness, CLI 등록, runner 비참조.
