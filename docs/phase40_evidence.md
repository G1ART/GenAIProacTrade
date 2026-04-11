# Phase 40 evidence — family PIT spec bindings

## 추가로 꼭 해야 할 일?

- `phase40_bundle_written` / `phase40_review_written` 확인
- `docs/operator_closeout/phase40_family_spec_bindings_bundle.json` 이 유효 JSON이고 `"ok": true`
- (선택) `promotion_gate_history_v1.json` 에 Phase 40 엔트리 append 정상 여부
- Phase 41 실행 후: **`docs/phase41_evidence.md`**, `phase42` 권고는 Phase 41 번들

## 실측 클로즈아웃

**명령**: `run-phase40-family-spec-bindings --universe sp500_current` (산출 경로는 패치 보고서 CLI 절 참고)

근거: `docs/operator_closeout/phase40_family_spec_bindings_bundle.json`, `phase40_family_spec_bindings_review.md`, `phase40_explanation_surface_v3.md`.

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-11T00:09:06.788705+00:00` |
| `pit_execution.experiment_id` | `b0ed1cdd-19ee-448a-9748-a295784a9a94` |
| `pit_execution.fixture_row_count` | **8** |
| `runs_resolved.baseline_run_id` / `alternate_run_id` | `223e2aa5-3879-4dee-b28f-3d579cbf4cbd` / `39208f19-8d0e-4c35-9950-78963bb59a97` |
| `runs_resolved.completed_runs_considered` | **13** |
| `scores_loaded` (baseline / alternate) | **353** / **313** |
| `families_executed_count` | **5** |
| `implemented_family_spec_count` | **7** |
| `all_families_leakage_passed` | **true** |
| 패밀리별 `joined_any_row` | **전부 false** (`pit_execution.families_executed` · `family_level_summary`) |
| 행 단위 outcome (각 패밀리·각 spec) | **`still_join_key_mismatch` 8**; joined / other_exclusion / invalid **0** |
| `lifecycle_status_distribution` (after) | `challenged`: **1**, `conditionally_supported`: **4** |
| `adversarial_reviews_after_count` | **8** |
| `adversarial_review_count_by_family_tag` | `score_publication_cadence_v1`·`signal_filing_boundary_v1`·`governance_join_policy_v1`·`issuer_sector_reporting_cadence_v1` 각 **1** |
| `promotion_gate_phase40.gate_status` | `deferred` |
| `promotion_gate_phase40.primary_block_category` | `conditionally_supported_but_not_promotable` |
| `phase41_recommendation` | `wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4` |

### 구현 참고 (롤업 버그 수정)

이전에는 `pit_as_of_boundary_v1`의 `summary_counts_by_spec`만 **1행으로 잘못 집계**되는 경우가 있었음 (`rollup_standard` 입력 dict 키 충돌). **`src/phase40/family_execution.py`** 에서 행 인덱스를 키로 두도록 수정함. 재실행 시 동일 로직으로 번들이 생성됨.

## 산출 파일

- `docs/operator_closeout/phase40_family_spec_bindings_bundle.json`
- `docs/operator_closeout/phase40_family_spec_bindings_review.md`
- `docs/operator_closeout/phase40_explanation_surface_v3.md`
- `data/research_engine/hypotheses_v1.json`, `adversarial_reviews_v1.json`, `promotion_gate_v1.json`, `promotion_gate_history_v1.json`
- `data/research_engine/governance_join_policy_registry_v1.json` (정책 레지스트리)

## Related

`docs/phase40_patch_report.md`, `docs/phase39_evidence.md`, **`docs/phase41_evidence.md`** (Phase 41 실측), **`docs/phase42_evidence.md`** (Phase 42 증거 적층), `HANDOFF.md`
