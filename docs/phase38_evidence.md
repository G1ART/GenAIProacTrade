# Phase 38 evidence — DB-bound PIT

## 추가로 꼭 해야 할 일?

**필수는 없음.** 아래가 이미 있으면 Sprint 2 클로저로 충분하다.

- `phase38_bundle_written` / `phase38_review_written` 확인
- `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json` 이 유효 JSON이고 `"ok": true`
- (선택) `data/research_engine/*.json` 변경분을 커밋할지 팀 정책으로 결정
- (선택) Phase 39·40 스프린트: **`docs/phase39_evidence.md`**, Phase 39 번들 `phase40` 권고를 진입 조건으로 사용

---

## 실측 클로즈아웃 (`sp500_current`, 2026-04-10 UTC)

- **명령**: `run-phase38-db-bound-pit-runner --universe sp500_current` (기본 bundle/out-md 경로)
- **번들 `generated_utc`**: `2026-04-10T18:26:47.398074+00:00`
- **리뷰 MD 생성**: `2026-04-10T18:26:47.398780+00:00` (로컬 생성 시각; 번들과 동일 런)
- **실험 id (`pit_execution.experiment_id`)**: `41dea3b0-02fe-46d8-951d-e2778af01e9f`

### 해석된 `state_change_runs`

| 역할 | `run_id` |
|------|----------|
| Baseline (최신 completed) | `223e2aa5-3879-4dee-b28f-3d579cbf4cbd` |
| Alternate (직전 completed) | `39208f19-8d0e-4c35-9950-78963bb59a97` |
| 고려된 completed 런 수 | 13 |

### 로드한 점수 행 수

- **baseline 런**: 353행 (`scores_loaded.baseline`)
- **alternate 런**: 313행 (`scores_loaded.alternate`)
- **`state_change_scores_limit`**: 50_000 (요청 상한; 실제는 위와 같음)

### 픽스처 8행 — 스펙별 결과 (요약)

세 스펙 모두 **행당 `still_join_key_mismatch` 8/8** (raw `summary_counts` 동일).

표준 네 버킷 롤업(`summary_counts_standard`): baseline / lag / alternate 각각  
`still_join_key_mismatch: 8`, 나머지(`reclassified_to_joined`, `reclassified_to_other_exclusion`, `invalid_due_to_leakage_or_non_pit`) **전부 0**.

- **Lag**: `lag_calendar_days` = 7 (시그널일 + 7일 캘린더 상한).

### 누수 감사

- **`leakage_audit.passed`**: `true`
- **`violations`**: 0건

### 적대적 리뷰 (증거 반영)

- **`phase38_resolution_status`**: `deferred_with_evidence_reinforces_baseline_mismatch`
- **`phase38_leakage_audit_passed`**: `true`
- **요지**: baseline·lag에서 픽스처가 `join_key_mismatch` 유지; alternate(이전 런)에서도 joined로 바뀌지 않음. 원 챌린지(대안 런 룩어헤드)는 문서화·추가 거버넌스 스펙까지 **완전 해소는 아님**.

### 프로모션 게이트 v1

- **`gate_status`**: `blocked`
- **주요 `blocking_reasons`**: `hypothesis_under_test_not_eligible_for_product_promotion`, `adversarial_challenge_not_cleared`

### 케이스북

- **`case_pit_no_sc_join_key_mismatch_8`** 메타에 `phase38_*` 필드 및 `better_understood: true` 반영 (번들 `casebook_update_summary` 참고).

### Phase 39 권고 (본 런)

- **`phase39_recommendation`**: `broaden_hypothesis_families_and_harden_explanation_under_persistent_mismatch`
- **요지**: 실행된 스펙에서 픽스처가 계속 `join_key_mismatch` → 이 솔기만으로는 부족; 가설 패밀리 확장 + PIT 경계 설명 강화.

---

## 전제 (일반)

- **실 DB** (`issuer_state_change_scores`, `state_change_runs`) 접근이 있어야 `run-phase38-db-bound-pit-runner` 가 의미 있다.
- 픽스처는 Phase 37과 동일한 **8행 `join_key_mismatch`** (`fixture_join_key_mismatch_rows`).

## 실행된 스pec (설계)

1. **baseline_production_equivalent** — `bisect_right` 픽 (Phase 36 잔여 감사와 동일 규칙).
2. **alternate_prior_completed_run** — 동일 유니버스 **두 번째** completed 런(없으면 스킵).
3. **lag_calendar_signal_bound** — baseline 점수 + 시그널일 + N 캘린더일 상한.

## 집계 버킷 (표준 네 가지)

`still_join_key_mismatch` · `reclassified_to_joined` · `reclassified_to_other_exclusion` · `invalid_due_to_leakage_or_non_pit`

`alternate_spec_not_executed` 는 표준 롤업에서 제외.

## 산출 파일

- `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json`
- `docs/operator_closeout/phase38_db_bound_pit_runner_review.md`
- `docs/operator_closeout/phase38_explanation_surface.md`
- 갱신: `data/research_engine/adversarial_reviews_v1.json`, `casebook_v1.json`, `promotion_gate_v1.json`

## Related

- `docs/phase38_patch_report.md`
- `docs/phase37_evidence.md`
- `docs/phase39_evidence.md` — Phase 39 클로즈아웃·게이트 이력·가설 패밀리 실측
- `HANDOFF.md`

## Tests (DB 없음)

```bash
pytest src/tests/test_phase38_pit_join_logic.py -q
```
