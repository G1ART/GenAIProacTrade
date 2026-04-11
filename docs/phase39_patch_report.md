# Phase 39 패치 보고 — hypothesis family expansion

## 목적

Phase 38 실측(누수 통과·8행 지속 `join_key_mismatch`)에 대응해 **단일 가설에 머물지 않도록** bounded research family를 도입하고, **라이프사이클 감사**, **다중 stance 적대적 리뷰**, **PIT 패밀리 계약**, **라이프사이클 연동 프로모션 게이트**, **설명 v2**를 한 CLI 사이클로 반영한다. 광역 기판 수리·자동 승격·제네릭 추천 UI는 비목표.

## 모듈 (`src/phase39/`)

| 모듈 | 역할 |
|------|------|
| `hypothesis_seeds` | 동일 8행 픽스처용 가설 4건 추가 (전부 `draft`) |
| `lifecycle` | `lifecycle_transitions` append-only 전환 |
| `adversarial_batch` | lineage 유지 + `skeptical_*` / `regime_horizon_reviewer` append (idempotent) |
| `pit_family_contract` | 공유 row 스키마·누수 규칙·패밀리별 spec 바인딩 요약 |
| `promotion_gate_phase39` | `primary_block_category` 3분류 + 이력 append |
| `explanation_v2` | 경쟁 가설·검증 범위·미해결·비투자조언 문구 |
| `phase40_recommend` | Phase 40 권고 문자열 |
| `orchestrator` | Phase 38 번들 읽기 → 영속 JSON 갱신 → 번들 코어 |
| `review` | 클로즈아웃 JSON·MD |

## CLI

- `run-phase39-hypothesis-family-expansion` — `--phase38-bundle-in`, `--research-data-dir`, `--explanation-out`, `--gate-history-filename`, `--bundle-out`, `--out-md`
- `write-phase39-hypothesis-family-expansion-review` — `--bundle-in`

성공 시: **`phase39_bundle_written`**, **`phase39_review_written`**

## Phase 37/38 정리

- `HypothesisStatus`: `conditionally_supported` 추가; `HypothesisV1.lifecycle_transitions`
- `ReviewerStance`: `skeptical_fundamental`, `skeptical_quant`, `regime_horizon_reviewer`
- `phase37.constitution.RESEARCH_ENGINE_ARTIFACTS`: phase39 모듈·`promotion_gate_history_v1.json` 반영

## 실측 (저장소 번들 기준, 2026-04-10)

- **번들 `generated_utc`**: `2026-04-10T21:28:28.683360+00:00`
- **가설 5**, 분포: `challenged` 1 / `draft` 4
- **적대적 stance**: lineage 1 + Phase 39 배치 3
- **게이트**: `gate_status` `deferred`, `primary_block_category` `deferred_pending_more_hypothesis_coverage`
- **게이트 이력**: `promotion_gate_history_v1.json` 에 **2**건 누적(동일 월 내 CLI 2회 실행)
- **Phase 40**: `implement_pit_family_spec_bindings_and_rerun_db_runner_under_shared_leakage_audit`

## 테스트

`pytest src/tests/test_phase39_hypothesis_family.py -q`
