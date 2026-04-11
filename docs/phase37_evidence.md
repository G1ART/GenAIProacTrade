# Phase 37 evidence (Sprint 1 — research engine scaffold)

## CLI가 정상인지 판별하는 법

다음이면 **성공**으로 본다.

1. Exit code **0**
2. stdout에 **`phase37_bundle_written`** 와 **`phase37_review_written`** 가 각각 한 번 이상
3. `docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json` 이 **유효 JSON**이고 `"ok": true`

긴 JSON을 터미널에 그대로 출력하면 **줄 폭 때문에** 같은 키가 두 줄로 잘려 **중복 출력처럼 보이는** 경우가 있다. **파일 내용이 근거이며**, 터미널 캡처만으로는 손상 여부를 판단하지 않는다. 검증:

```bash
python3 -c "import json; json.load(open('docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json')); print('OK')"
```

## 운영자 추가 액션

**필수 없음.** Sprint 1은 DB·광역 수리 없이 로컬 파일만 갱신한다.

- **선택**: `data/research_engine/*.json` 을 버전 관리에 포함할지(팀 정책).
- **선택**: Phase 36.1 번들 경로가 다르면 `--phase36-1-bundle-in` 만 맞춘다. 번들이 없어도 오케스트레이터는 **기본 ground_truth 폴백**으로 동작한다.

## 실측 런 (예시)

- **명령**: `run-phase37-research-engine-backlog-sprint` + `--phase36-1-bundle-in docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`
- **번들 `generated_utc` (저장소 기록 예)**: `2026-04-10T16:46:00.732862+00:00`
- **Phase 36.1 ground_truth** (번들에 포함): `joined` 266, `joined_market_metadata_flagged` 0, `no_state_change_join` 8, freeze / phase37 권고 유지

## 스프린트 산출 요약

| 항목 | 수량 / 상태 |
|------|-------------|
| 가설 (`hypothesis_registry_v1`) | 1 (`under_test`) |
| PIT 실험 기록 | 1 (`recorded_scaffold`, DB 미실행) |
| 적대적 리뷰 | 1 |
| 케이스북 | 4 (PIT 8, GIS, NQ 7, 레지스트리 tail) |
| 설명 프로토타입 | `phase37_explanation_prototype.md` |
| Phase 38 권고 | `bind_pit_experiment_runner_to_db_and_execute_alternate_as_of_specs` |

## 성공 기준 대조 (워크오더)

- 기판 수리 모드에서 연구 엔진 빌드 모드로 전환됨 → **constitution + 모듈 + 번들**
- 실행 가능 가설 객체 ≥ 1 → **충족**
- PIT-lab 실험 스캐폴드 ≥ 1 → **충족** (DB 바인딩은 Phase 38)
- 잔여 tail이 케이스북 엔트리로 저장 → **4건**
- 사용자 설명 프로토타입 ≥ 1 → **충족**

## Related

- `docs/phase37_patch_report.md`
- `docs/research_engine_constitution.md`
- `HANDOFF.md` (상단 요약 + **HANDOFF — Phase 37**)
- `docs/phase36_evidence.md` (기판 freeze 근거)

## Tests

```bash
pytest src/tests/test_phase37_research_engine.py -q
```
