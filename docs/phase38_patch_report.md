# Phase 38 패치 보고 — DB-bound PIT runner

## 목적

Phase 37 스캐폴드를 **실제 DB 조회**와 닫힌 루프로 연결한다: 가설 → 결정적 PIT 재현 → **baseline / alternate run / lag signal bound** 비교 → 적대적 리뷰 갱신 → **프로모션 게이트 v1** → 케이스북·설명면 갱신. 광역 기판 수리·다수 가설 확장·자동 승격·제네릭 UI는 비목표.

## 모듈

| 모듈 | 역할 |
|------|------|
| `phase38.pit_join_logic` | `pick_state_change_at_or_before_signal` (Phase 36 잔여 조인과 동일 규칙) |
| `phase38.pit_runner` | `issuer_state_change_scores` 로드, 3 스펙 실행, 누수 감사 |
| `phase38.adversarial_update` | 기존 챌린지 보존 + `phase38_resolution_status` 등 |
| `phase38.promotion_gate_v1` | 게이트 구조화 레코드 |
| `phase38.phase39_recommend` | Phase 39 권고 |
| `phase38.explanation_phase38` | 실행 결과 반영 설명 MD |
| `phase38.orchestrator` | 전체 조립, `data/research_engine/*.json` 갱신 |
| `phase38.review` | 클로즈아웃 MD·JSON |

## CLI

- `run-phase38-db-bound-pit-runner` — `p27` (`--universe` 필수), `--state-change-scores-limit`, `--lag-calendar-days`, `--baseline-run-id`, `--alternate-run-id`, `--research-data-dir`, `--explanation-out`, `--bundle-out`, `--out-md`
- `write-phase38-db-bound-pit-runner-review` — `--bundle-in`

성공 시: **`phase38_bundle_written`**, **`phase38_review_written`**

## 산출물

- `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json`
- `docs/operator_closeout/phase38_db_bound_pit_runner_review.md`
- `docs/operator_closeout/phase38_explanation_surface.md`
- 갱신: `data/research_engine/adversarial_reviews_v1.json`, `casebook_v1.json`, **`promotion_gate_v1.json`**

## 재현

```bash
export PYTHONPATH=src
python3 src/main.py run-phase38-db-bound-pit-runner \
  --universe sp500_current \
  --bundle-out docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json \
  --out-md docs/operator_closeout/phase38_db_bound_pit_runner_review.md
```

(Supabase/DB 접근 필요)

## 테스트

`pytest src/tests/test_phase38_pit_join_logic.py -q`

## 실측 (`sp500_current`, 2026-04-10)

- **근거**: `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json` (`generated_utc` `2026-04-10T18:26:47.398074+00:00`).
- **실험 id**: `41dea3b0-02fe-46d8-951d-e2778af01e9f`.
- **런**: baseline `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`, alternate `39208f19-8d0e-4c35-9950-78963bb59a97`; completed 후보 13건.
- **점수 로드**: baseline 353행, alternate 313행.
- **8행 픽스처**: 세 스펙 모두 **`still_join_key_mismatch` 8/8**; 표준 롤업에서 joined / other_exclusion / invalid **0**.
- **누수 감사**: **통과**, violations 0.
- **적대적 리뷰**: `deferred_with_evidence_reinforces_baseline_mismatch`.
- **게이트**: `blocked` (가설 under_test + 챌린지 미해소).
- **Phase 39**: `broaden_hypothesis_families_and_harden_explanation_under_persistent_mismatch`.

## Phase 39 (번들 `phase39` 일반)

증거에 따라 `broaden_hypothesis_families…`, `encode_governance_safe_alternate_specs…`, `reconcile_fixture_baseline_divergence…`, `remediate_pit_join_leakage…` 등으로 분기 — **본 저장소 실측은 위 Phase 39 권고**를 따름.
