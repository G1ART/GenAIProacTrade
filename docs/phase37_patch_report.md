# Phase 37 패치 보고 — Research engine backlog sprint 1

## 목적

공개 코어 기판 **MVP freeze** 이후, **기판 광역 수리를 헤드라인으로 두지 않고** 상위 **연구 엔진** 레이어(가설·PIT 실험실·적대적 리뷰·케이스북·설명)의 **실행 가능한 스캐폴드**를 추가한다. 스코어·임계 완화·프리미엄 데이터 확장·자동 가설 승격은 비목표.

## 모듈

| 파일 | 역할 |
|------|------|
| `phase37.constitution` | 6필러, 모듈·JSON 경로, work_unit_types (`RESEARCH_ENGINE_ARTIFACTS`) |
| `phase37.hypothesis_registry` | `HypothesisV1` + 시드 1건 (`under_test`) |
| `phase37.pit_experiment` | `PITRunSpecV1`, 스캐폴드 기록, join_key_mismatch 8행 픽스처 |
| `phase37.adversarial_review` | 구조화 리뷰 레코드 |
| `phase37.casebook` | 잔여 tail 4케이스 시드 |
| `phase37.explanation_surface` | 가설+시그널 행에서 설명 MD 생성 |
| `phase37.orchestrator` | 번들 조립, `data/research_engine/*.json` 갱신 |
| `phase37.review` | 클로즈아웃 MD·JSON |
| `phase37.phase38_recommend` | Phase 38 권고 |

## CLI

| 명령 | 설명 |
|------|------|
| `run-phase37-research-engine-backlog-sprint` | 전 스캐폴드 실행 (기본 bundle/out-md 경로 내장) |
| `write-phase37-research-engine-backlog-sprint-review` | 번들에서 review MD 재생성 |

성공 시 stdout: **`phase37_bundle_written`**, **`phase37_review_written`**. 이어지는 전체 JSON은 터미널 폭 때문에 줄이 겹쳐 보일 수 있음. **근거는 파일.**

## 산출물

- `docs/research_engine_constitution.md`
- `docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json`
- `docs/operator_closeout/phase37_research_engine_backlog_sprint_review.md`
- `docs/operator_closeout/phase37_explanation_prototype.md`
- `data/research_engine/hypotheses_v1.json`, `casebook_v1.json`, `pit_experiments_v1.json`, `adversarial_reviews_v1.json`

## 재현

```bash
export PYTHONPATH=src
python3 src/main.py run-phase37-research-engine-backlog-sprint \
  --phase36-1-bundle-in docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json \
  --bundle-out docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json \
  --out-md docs/operator_closeout/phase37_research_engine_backlog_sprint_review.md
```

## 테스트

`pytest src/tests/test_phase37_research_engine.py -q`

## Phase 38

번들 필드 `phase38.phase38_recommendation`: **`bind_pit_experiment_runner_to_db_and_execute_alternate_as_of_specs`**
