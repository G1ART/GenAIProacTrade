# Phase 51 evidence — external trigger ingest & runtime health surface

## 운영 클로즈

- **상태**: **종료 (operational closeout)** — 2026-04-13 UTC 기준 권위 번들 `generated_utc` 및 아래 실측 행 참고.
- **한 페이지 요약**: `docs/operator_closeout/phase51_closeout.md`

## 확인 체크리스트

- `run-phase51-external-positive-path-smoke` 성공 시 stdout JSON `ok: true`, `smoke_metrics_ok: true` — 외부 이벤트 1건 이상 **승인** 후 사이클에 소비, 잡 생성·실행≥1, 토론·프리미엄·디스커버리·cockpit 중 최소 하나 비영
- stdout에 `phase51_bundle_written`, `phase51_review_written`, `phase51_health_review_written` (기본 `--bundle-out` / `--out-md` / `--out-md-health` 사용 시)
- `--persist-runtime-health` 사용 시 `data/research_runtime/runtime_health_summary_v1.json` 갱신
- 지속·격리 산출: 스모크 전용 `data/research_runtime/phase51_external_*_v1.json`, `phase51_smoke_*`; 운영 적재는 `external_trigger_ingest_v1.json`, `external_trigger_audit_log_v1.json` (첫 적재 시 생성)
- `pytest src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py -q`
- 기판 수리·무제한 웹훅 플러드·자율 매매 **없음**

## 산출물 (권위 번들·리뷰)

| 산출물 | 경로 |
|--------|------|
| Phase 51 외부 인제스트·스모크 번들 | `docs/operator_closeout/phase51_external_trigger_ingest_bundle.json` |
| 위 리뷰 MD | `docs/operator_closeout/phase51_external_trigger_ingest_review.md` |
| 런타임 헬스 표면 리뷰 MD | `docs/operator_closeout/phase51_runtime_health_surface_review.md` |

## 저장소 기록 실측 (2026-04-13 — 운영자 CLI)

명령:

```bash
PYTHONPATH=src python3 src/main.py run-phase51-external-positive-path-smoke --persist-runtime-health
```

| 필드 | 값 |
|------|-----|
| 번들 `generated_utc` | `2026-04-13T06:38:15.299044+00:00` |
| `ok` | `true` |
| `smoke_metrics_ok` | `true` |
| Phase 50 제어 번들 입력 | `docs/operator_closeout/phase50_registry_controls_and_operator_timing_bundle.json` |
| Phase 46 입력 (오케스트레이터 기본) | `docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json` |
| `external_events_received` | `1` |
| `external_events_accepted` | `1` |
| `external_events_rejected` | `0` |
| `external_events_deduped` | `0` |
| 정규화 결과 | `manual_watchlist` ← `watchlist_submit`, `accepted_governed` |
| `cycles_consuming_external_events` | `f36b11ba-f3e9-4d6e-902c-f24fcbe396c1` |
| Phase 48 `phase48_generated_utc` | `2026-04-13T06:38:15.297941+00:00` |
| 트리거 | `manual_watchlist` (dedupe `ext:file_drop:phase51_external_positive_path:watchlist_submit:…`) |
| 잡 | `debate.execute` — 생성 1, 실행 1 |
| 토론 outcome | `unknown` (`policy_max_turns_reached`) |
| `runtime_health_summary.health_status` | `healthy` |
| 감사 `why_cycle_started` | `phase51_external_positive_path` |
| Phase 52 | **종료** — 동일 권고 토큰으로 구현·클로즈 (`docs/phase52_evidence.md`, `docs/operator_closeout/phase52_closeout.md`) |
| Phase 53 권고 | `signed_payload_hmac_source_rotation_and_dead_letter_replay_v1` |

격리 파일 (스모크 실행 시 갱신되는 경로 예시):

- `data/research_runtime/phase51_external_drop_smoke_v1.json`
- `data/research_runtime/phase51_external_smoke_ingest_v1.json`
- `data/research_runtime/phase51_external_smoke_audit_v1.json`
- `data/research_runtime/phase51_external_smoke_registry_v1.json`
- `data/research_runtime/phase51_external_smoke_discovery_v1.json`

## Cockpit·API

- `GET /api/overview` → `runtime_health` (한글 헤드라인·plain lines + `advanced`)
- `GET /api/runtime/health`, `POST /api/runtime/external-ingest` (본문 ≤ 32768 bytes)

## Related

`docs/phase51_patch_report.md`, `docs/operator_closeout/phase51_closeout.md`, `docs/phase50_evidence.md`, `docs/phase52_evidence.md`, `docs/operator_closeout/phase52_closeout.md`, `HANDOFF.md`, `docs/research_engine_constitution.md`
