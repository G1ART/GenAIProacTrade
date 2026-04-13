# Phase 48 evidence — proactive research runtime (single cycle)

## 클로즈아웃

- **상태**: **종료** — Phase 49 다중 사이클 CLI가 **실행·검증**되었으며, Phase 48 단일 사이클 런타임은 **유지 컴포넌트**로 남는다.
- **운영 클로즈 요약**: `docs/operator_closeout/phase48_closeout.md`
- **Phase 49 수락 실행 (저장소 기록)**: `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json` (`generated_utc` `2026-04-13T01:10:08.591610+00:00`, `ok: true`) · `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`

## 확인 체크리스트

- `run-phase48-proactive-research-runtime` 성공 시 stdout JSON `ok: true`
- `phase48_bundle_written` / `phase48_review_written`
- `data/research_runtime/research_job_registry_v1.json` 에 job 이력 누적(사이클마다 갱신)
- `pytest src/tests/test_phase48_proactive_research_runtime.py -q`
- 기판·DB 수리 **없음** (정적 번들 + 레저만 읽음)

## 산출물

| 산출물 | 경로 |
|--------|------|
| 사이클 번들 | `docs/operator_closeout/phase48_proactive_research_runtime_bundle.json` |
| 리뷰 | `docs/operator_closeout/phase48_proactive_research_runtime_review.md` |
| 잡 레지스트리 | `data/research_runtime/research_job_registry_v1.json` |
| 디스커버리 후보 | `data/research_runtime/discovery_candidates_v1.json` |

## 저장소 기록

| 필드 | 값 |
|------|-----|
| 단일 사이클 `generated_utc` (권위 번들) | `2026-04-13T00:50:42.691404+00:00` |
| 입력 Phase 46 | `phase46_founder_decision_cockpit_bundle.json` |
| `phase49.phase49_recommendation` | `daemon_scheduler_multi_cycle_triggers_and_metrics_v1` |
| Phase 49 집계 번들 `generated_utc` (클로즈 검증) | `2026-04-13T01:10:08.591610+00:00` |

## 트리거 (현재 구현)

| 유형 | 요약 |
|------|------|
| `changed_artifact_bundle` | 레지스트리의 `last_phase46_generated_utc` ≠ 현재 번들 `generated_utc` |
| `operator_research_signal` | 결정 레저에 `last_cycle_utc` 이후 `watch` / `reopen_request` |
| `closeout_reopen_candidate` | 동일 구간의 `reopen_request` |
| `named_source_signal` | 클로즈아웃·명명 소스 전제 + 노트에 `named`/`source` 토큰 |
| `manual_watchlist` | `data/research_runtime/manual_triggers_v1.json` 의 `pending[]` (잡 생성 시 소비·비움) |

## Related

`docs/phase48_patch_report.md`, `docs/operator_closeout/phase48_closeout.md`, `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`, `docs/phase47_evidence.md`, `docs/phase46_evidence.md`, `HANDOFF.md`, `docs/research_engine_constitution.md`
