# Phase 50 — 운영 클로즈아웃 (런타임 제어 평면 & positive-path 스모크)

**상태**: **종료 (closed)** — 2026-04-13 UTC 기준(권위 번들 `generated_utc` 참고).

## 범위

- **구현**: `src/phase50_runtime/` — 제어 평면, 사이클 리스, 타이밍 정책, 런타임 감사 로그, 트리거 병합, 스모크 오케스트레이터.
- **Phase 48 연동**: `budget_policy` / `manual_triggers_path` / 수동 `suggested_job_type` (허용 잡 타입만).
- **CLI**: `run-phase50-registry-controls-and-operator-timing`, `run-phase50-positive-path-smoke`.
- **비목표**: 광역 기판 수리, DB 캠페인, 항상 켜진 무제한 데몬, 매매 직접 공표, 프리미엄 자동 구매.

## 수락 기준 (충족)

1. 제어 평면 파일 지속: `data/research_runtime/runtime_control_plane_v1.json`
2. 리스·stale 처리: `cycle_lease_v1.json`
3. 타이밍 정책으로 실행/스킵 설명 가능 (`timing_policy`)
4. 감사 로그 append-only: `runtime_audit_log_v1.json`
5. 트리거 타입 enable/disable 병합: `trigger_controls.effective_budget_policy`
6. **권위 스모크 비영**: `phase50_positive_path_smoke_bundle.json` 에 `smoke_metrics_ok: true`, `ok: true` — 최소 트리거 1·잡 생성·실행 1·(토론/프리미엄/디스커버리/cockpit 중 비영)
7. 제어 평면 클로즈 번들: `phase50_registry_controls_and_operator_timing_bundle.json` + 리뷰 MD

저장소에 기록된 예시 타임스탬프:

- 제어 평면 번들: `generated_utc` **`2026-04-13T05:50:40.090764+00:00`**
- 스모크 번들: `generated_utc` **`2026-04-13T05:50:46.368148+00:00`**

## 후속 (Phase 50 밖)

- **Phase 51**: `external_trigger_ingest_hooks_and_runtime_health_surface_v1` — 외부 인제스트·런타임 헬스 표면 등 (`phase50_registry_controls_and_operator_timing_bundle.json` 내 `phase51`).

## 참고

- 증거·체크리스트: **`docs/phase50_evidence.md`**
- 패치 보고: **`docs/phase50_patch_report.md`**
- 핸드오프: **`HANDOFF.md`** — Phase 50 절
- 헌장·명령: **`docs/research_engine_constitution.md`**
