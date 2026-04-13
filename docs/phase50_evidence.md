# Phase 50 evidence — runtime control plane & positive-path smoke

## 운영 클로즈

- **상태**: **종료 (operational closeout)** — 제어 평면·리스·감사·타이밍 정책·트리거 병합 및 **권위 있는 비영(non-empty) 스모크** 번들로 수락.
- **한 페이지 요약**: `docs/operator_closeout/phase50_closeout.md`

## 확인 체크리스트

- `run-phase50-registry-controls-and-operator-timing` 성공 시 stdout JSON `ok: true`, `phase50_registry_bundle_written` / `phase50_registry_review_written` (해당 플래그 사용 시)
- `run-phase50-positive-path-smoke` 성공 시 `smoke_metrics_ok: true`, `ok: true` — 트리거≥1, 잡 생성·실행≥1, 토론·프리미엄·디스커버리·cockpit 표면 중 최소 하나 비영
- 지속 파일 존재·갱신: `data/research_runtime/runtime_control_plane_v1.json`, `cycle_lease_v1.json`, `runtime_audit_log_v1.json`
- `pytest src/tests/test_phase50_registry_controls_and_operator_timing.py -q`
- 기판·DB 캠페인·무제한 데몬 **없음**

## 산출물 (권위 번들)

| 산출물 | 경로 |
|--------|------|
| 제어 평면·타이밍·감사 요약 번들 | `docs/operator_closeout/phase50_registry_controls_and_operator_timing_bundle.json` |
| 위 리뷰 MD | `docs/operator_closeout/phase50_registry_controls_and_operator_timing_review.md` |
| Positive-path 스모크 번들 | `docs/operator_closeout/phase50_positive_path_smoke_bundle.json` |
| 위 리뷰 MD | `docs/operator_closeout/phase50_positive_path_smoke_review.md` |

## 저장소 기록 (예시 — 재실행 시 번들의 `generated_utc` 가 갱신됨)

| 필드 | 값 (현재 저장소 스냅샷) |
|------|-------------------------|
| 제어 평면 번들 `generated_utc` | `2026-04-13T05:50:40.090764+00:00` |
| 스모크 번들 `generated_utc` | `2026-04-13T05:50:46.368148+00:00` |
| 스모크 `seeded_trigger_source` | `manual_watchlist` |
| 스모크 `seeded_job_type` | `debate.execute` |
| 스모크 `smoke_metrics_ok` | `true` |
| Phase 49 입력 (제어 평면 번들) | `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json` |
| Phase 46 입력 (스모크) | `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json` |
| Phase 51 권고 | `external_trigger_ingest_hooks_and_runtime_health_surface_v1` |

## 시드·거버넌스 (스모크)

- 격리 레지스트리·디스커버리·수동 트리거 파일로 **메인** `research_job_registry_v1.json` 과 혼선 최소화.
- 레지스트리 메타 `last_phase46_generated_utc` 를 Phase 46 번들과 정합시켜 **의도치 않은 `changed_artifact_bundle` 단독 트리거** 방지.
- 수동 항목의 `suggested_job_type` 은 **허용된 `JOB_TYPES`** 안에서만 적용(Phase 48 트리거 엔진).

## Related

`docs/phase50_patch_report.md`, `docs/operator_closeout/phase50_closeout.md`, `docs/phase48_evidence.md`, `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`, `HANDOFF.md`, `docs/research_engine_constitution.md`
