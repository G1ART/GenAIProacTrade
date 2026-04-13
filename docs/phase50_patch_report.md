# Phase 50 patch report — runtime control plane & positive-path smoke

## 목적

Phase 48/49 아키텍처 위에 **운영 제어 평면**(케이던스·트리거 on/off·윈도 캡)·**사이클 리스**(중복 호출 방지)·**append-only 런타임 감사 로그**를 두고, **운영자 시드·거버넌스 하의 비영 스모크** 번들로 선행 루프가 실제 산출을 낸다는 것을 권위 문서로 남긴다. **광역 기판·DB 수리·무제한 에이전트 루프 없음.**

## 코드·데이터

| 경로 | 역할 |
|------|------|
| `src/phase50_runtime/control_plane.py` | `runtime_control_plane_v1.json` |
| `src/phase50_runtime/cycle_lease.py` | `cycle_lease_v1.json` |
| `src/phase50_runtime/timing_policy.py` | 프로파일·`should_run_cycle_now` |
| `src/phase50_runtime/runtime_audit_log.py` | `runtime_audit_log_v1.json` |
| `src/phase50_runtime/trigger_controls.py` | 제어 평면 + 예산 정책 병합 |
| `src/phase50_runtime/orchestrator.py`, `review.py`, `phase51_recommend.py` | 번들·Phase 51 토큰 |
| `src/phase48_runtime/trigger_engine.py` | 선택 `manual_triggers_path`, 수동 `suggested_job_type` |
| `src/phase48_runtime/orchestrator.py` | `budget_policy`, `manual_triggers_path` 전달 |
| `src/main.py` | `run-phase50-registry-controls-and-operator-timing`, `run-phase50-positive-path-smoke` |
| `data/research_runtime/phase50_positive_path_smoke_*_v1.json` | 스모크 격리 산출 |

## CLI

**제어 평면·감사 요약 번들**

```bash
export PYTHONPATH=src
python3 src/main.py run-phase50-registry-controls-and-operator-timing \
  --phase49-bundle-in docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json \
  --bundle-out docs/operator_closeout/phase50_registry_controls_and_operator_timing_bundle.json \
  --out-md docs/operator_closeout/phase50_registry_controls_and_operator_timing_review.md
```

**Positive-path 스모크**

```bash
export PYTHONPATH=src
python3 src/main.py run-phase50-positive-path-smoke \
  --phase46-bundle-in docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json \
  --bundle-out docs/operator_closeout/phase50_positive_path_smoke_bundle.json \
  --out-md docs/operator_closeout/phase50_positive_path_smoke_review.md
```

선택: `--strict-timing`, `--no-skip-alerts`, `--registry-path`, `--discovery-path`, `--decision-ledger-path`

## 테스트

```bash
pytest src/tests/test_phase50_registry_controls_and_operator_timing.py -q
```

## 클로즈

- **Phase 50**: **종료** — 증거 `docs/phase50_evidence.md`, 요약 `docs/operator_closeout/phase50_closeout.md`.

## Related

`docs/phase50_evidence.md`, `docs/operator_closeout/phase50_closeout.md`, `docs/phase48_patch_report.md`, `HANDOFF.md`
