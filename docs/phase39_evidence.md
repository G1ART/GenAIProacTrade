# Phase 39 evidence — hypothesis family expansion + governance

## 추가로 꼭 해야 할 일?

**필수는 없음.** 아래가 있으면 Phase 39 클로즈아웃으로 충분하다.

- `phase39_bundle_written` / `phase39_review_written` 확인
- `docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json` 이 유효 JSON이고 `"ok": true`
- (선택) `promotion_gate_history_v1.json` 항목 누적은 **CLI 재실행 시 정상**(append-only)
- (선택) Phase 40은 번들 `phase40.phase40_recommendation` 을 진입 조건으로 사용

---

## 실측 클로즈아웃 (최신 번들, 2026-04-10 UTC)

**근거**: `docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json`

| 필드 | 값 |
|------|-----|
| `generated_utc` | `2026-04-10T21:28:28.683360+00:00` |
| 리뷰 MD 생성 UTC | `2026-04-10T21:28:28.683688+00:00` |
| 입력 Phase 38 번들 | `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json` |

### Phase 38 요약 (번들 입력)

- `pit_ok`: true, `leakage_passed`: true
- `experiment_id`: `41dea3b0-02fe-46d8-951d-e2778af01e9f`
- `phase38_resolution_status`: `deferred_with_evidence_reinforces_baseline_mismatch`
- `fixture_still_mismatch_all_specs`: true

### 가설

- **총계**: 5 (`hypothesis_family_count`)
- **분포**: `challenged` 1, `draft` 4

원가설 `hyp_pit_join_key_mismatch_as_of_boundary_v1` 은 `under_test`에서 `challenged`로 전환. `lifecycle_transitions` 최초 기록 시각은 첫 CLI 실행 기준 `2026-04-10T20:47:35.594122+00:00` (재실행 시 전환 중복 없음).

추가 4 ID: `hyp_score_publication_cadence_run_grid_lag_v1`, `hyp_signal_availability_filing_boundary_v1`, `hyp_issuer_sector_reporting_cadence_v1`, `hyp_governance_safe_alternate_join_policy_v1` — 모두 **draft**, 자동 승격 없음.

### 적대적 리뷰 (stance별)

- `data_lineage_auditor`: 1
- `skeptical_fundamental`: 1
- `skeptical_quant`: 1
- `regime_horizon_reviewer`: 1

### PIT family contract

- `contract_version`: 1, `fixture_class`: `join_key_mismatch_8`
- `family_bindings`: 5 (1 implemented 연동 + 4 planned)
- 누수 규칙: 패밀리 간 재사용 true

### 프로모션 게이트 (schema v2)

- `gate_status`: `deferred`
- `primary_block_category`: `deferred_pending_more_hypothesis_coverage`
- `draft_hypothesis_family_count`: 4, `primary_hypothesis_status`: `challenged`

### 게이트 이력

`data/research_engine/promotion_gate_history_v1.json` — **2**건 (`decision_utc` `2026-04-10T20:47:35.594395+00:00`, `2026-04-10T21:28:28.682838+00:00`). 재실행 시 엔트리 추가됨.

### Phase 40

`implement_pit_family_spec_bindings_and_rerun_db_runner_under_shared_leakage_audit` (번들 `phase40` 와 동일)

---

## 산출 파일

- `docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json`
- `docs/operator_closeout/phase39_hypothesis_family_expansion_review.md`
- `docs/operator_closeout/phase39_explanation_surface_v2.md`
- `data/research_engine/hypotheses_v1.json`, `adversarial_reviews_v1.json`, `promotion_gate_v1.json`, `promotion_gate_history_v1.json`

## Related

`docs/phase39_patch_report.md`, `docs/phase38_evidence.md`, `docs/phase40_evidence.md`, `docs/phase41_evidence.md`, `HANDOFF.md`

## Tests

```bash
pytest src/tests/test_phase39_hypothesis_family.py -q
```
