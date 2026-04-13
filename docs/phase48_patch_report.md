# Phase 48 patch report — proactive research runtime

## 목적

권위 번들·레저를 입력으로 **단일 사이클**의 선행 연구 루프를 돌린다. **트리거 → 잡 생성(상한) → 결정론적 실행 →(선택) 경계 토론 → 프리미엄 후보·디스커버리 후보 → cockpit 표면 레코드**까지. **무한 에이전트 루프·기판 수리·DB 캠페인 없음.**

## 코드·데이터

| 경로 | 역할 |
|------|------|
| `src/phase48_runtime/job_registry.py` | `research_job_registry_v1.json` |
| `src/phase48_runtime/trigger_engine.py` | 결정론적 트리거·중복 제거 |
| `src/phase48_runtime/bounded_debate.py` | 역할·턴 상한, outcome 분류 |
| `src/phase48_runtime/premium_escalation.py` | 프리미엄 **후보만** (강제 구매 없음) |
| `src/phase48_runtime/discovery_pipeline.py` | `discovery_candidates_v1.json` |
| `src/phase48_runtime/budget_policy.py` | 잡/턴/알림/후보 상한 |
| `src/phase48_runtime/orchestrator.py`, `review.py`, `phase49_recommend.py` | 사이클·산출 |
| `data/research_runtime/*.json` | 지속 상태 |
| `src/main.py` | `run-phase48-proactive-research-runtime` |

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py run-phase48-proactive-research-runtime \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase48_proactive_research_runtime_bundle.json \
  --out-md docs/operator_closeout/phase48_proactive_research_runtime_review.md
```

선택: `--skip-alerts`, `--registry-path`, `--discovery-path`, `--decision-ledger-path`

## 스케줄

한 번의 CLI 호출 = 한 사이클. cron/systemd에서 동일 명령 반복은 **Phase 49** `run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1` 로 N회·집계·슬립을 묶어 실행한다.

## 클로즈아웃

- **Phase 48**: **종료** — 단일 사이클 구현·테스트·저장소 단일 사이클 번들(`generated_utc` `2026-04-13T00:50:42.691404+00:00`) 및 Phase 49 실측 번들로 수락 완료. 요약: **`docs/operator_closeout/phase48_closeout.md`**.

## 테스트

```bash
pytest src/tests/test_phase48_proactive_research_runtime.py -q
```

## Related

`docs/phase48_evidence.md`, `docs/operator_closeout/phase48_closeout.md`, `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`, `HANDOFF.md`
