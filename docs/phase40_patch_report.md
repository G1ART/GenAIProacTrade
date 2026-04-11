# Phase 40 패치 보고 — PIT family spec bindings

## 목적

Phase 39의 패밀리 문법을 **실제 DB 결합 실행**으로 전환한다. 패밀리별 `spec_results` 동적 키·공통 네 가지 outcome 버킷·**동일 누수 감사 규칙**·라이프사이클·패밀리 단위 적대적 리뷰·게이트 schema v3·설명 v3. 광역 기판·자동 승격·제네릭 추천 UI 비목표.

## 모듈 (`src/phase40/`)

| 모듈 | 역할 |
|------|------|
| `pit_engine` | `classify_row_outcome`, `add_calendar_days`, `rollup_standard`, `STANDARD_BUCKETS` (Phase 38 `pit_runner` 도 재사용) |
| `family_execution` | `run_phase40_pit_families` — 5패밀리·동적 spec 키 |
| `contract_manifest` | 번들용 구현 스펙 요약 |
| `lifecycle_phase40` | draft → `conditionally_supported` / 누수 실패 시 `deferred` |
| `adversarial_family` | 패밀리별 가설에 리뷰 append (`phase40_family_execution_review`) |
| `promotion_gate_phase40` | `conditionally_supported_but_not_promotable` 등 |
| `explanation_v3` | 패밀리 비교·비투자조언 |
| `phase41_recommend` | Phase 41 권고 문자열 |
| `orchestrator` | Supabase + 영속 JSON + 설명 |
| `review` | 클로즈아웃 JSON·MD |

## 구현 스펙 (8행 픽스처)

| 패밀리 | spec_key |
|--------|----------|
| `pit_as_of_boundary_v1` | `baseline_production_equivalent`, `alternate_prior_completed_run`, `lag_calendar_signal_bound` |
| `score_publication_cadence_v1` | `run_completion_anchored_signal_bound` |
| `signal_filing_boundary_v1` | `filing_public_ts_strict_pick` (filing ts 부재 시 signal 프록시) |
| `governance_join_policy_v1` | `governance_registry_bound_pick` (`governance_join_policy_registry_v1.json`) |
| `issuer_sector_reporting_cadence_v1` | `stratified_fixture_only_replay` (픽스처 코호트만 baseline 동일 pick) |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase40-family-spec-bindings \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase40_family_spec_bindings_bundle.json \
  --out-md docs/operator_closeout/phase40_family_spec_bindings_review.md
```

(Supabase 필요)

## 테스트 (DB 없음)

`pytest src/tests/test_phase40_pit_engine.py src/tests/test_phase38_pit_join_logic.py -q`

## 실측

**번들** `docs/operator_closeout/phase40_family_spec_bindings_bundle.json` (`ok: true`).

- **UTC**: `generated_utc` `2026-04-11T00:09:06.788705+00:00`; `pit_execution.generated_utc` `2026-04-11T00:09:06.786048+00:00`
- **universe**: `sp500_current`
- **experiment_id**: `b0ed1cdd-19ee-448a-9748-a295784a9a94`
- **픽스처**: **8**행; baseline / alternate 런 동일 Phase 38 실측과 정합 (`223e2aa5…` / `39208f19…`, `scores_loaded` 353 / 313, `completed_runs_considered` 13)
- **실행 규모**: 패밀리 **5**, 구현 스펙 **7**; 패밀리별 `joined_any_row` **false**; 패밀리·스펙별 **`still_join_key_mismatch` 8** (표준 버킷 나머지 0)
- **누수**: `all_families_leakage_passed` **true**
- **라이프사이클 (after)**: `challenged` 1 · `conditionally_supported` 4
- **게이트 v3**: `deferred` / `conditionally_supported_but_not_promotable`
- **Phase 41 권고**: `wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4` — **실행·실측 완료** → **`docs/phase41_evidence.md`**, **`docs/phase41_patch_report.md`**

상세 표·산출 경로: **`docs/phase40_evidence.md`**. 리뷰 MD는 `write-phase40-family-spec-bindings-review --bundle-in …` 로 번들과 재동기화 가능.
