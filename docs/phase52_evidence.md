# Phase 52 evidence — governed webhook auth, budgets, routing, optional queue

## 운영 클로즈

- **상태**: **종료 (operational closeout)** — 2026-04-14 UTC 기준 권위 번들 `generated_utc` 및 아래 실측 표 참고.
- **한 페이지 요약**: `docs/operator_closeout/phase52_closeout.md`

## 확인 체크리스트

- `run-phase52-governed-webhook-auth-routing-smoke` 성공 시 stdout JSON `ok: true`, `smoke_metrics_ok: true`
- stdout에 `phase52_bundle_written`, `phase52_review_written`, `phase52_health_review_written` (기본 `--bundle-out` / `--out-md` / `--out-md-health` 사용 시)
- `--persist-runtime-health` 사용 시 `data/research_runtime/runtime_health_summary_v1.json` 갱신(운영 루트에 소스 레지스트리가 있으면 `external_source_activity_v52` 병합)
- `pytest src/tests/test_phase52_webhook_auth_routing.py -q` 및 Phase 51·50 회귀
- 기판 수리·무인증 공개 플러드·자율 매매 **없음**

## 산출물 (권위 번들·리뷰)

| 산출물 | 경로 |
|--------|------|
| Phase 52 웹훅·라우팅 번들 | `docs/operator_closeout/phase52_webhook_auth_routing_bundle.json` |
| 위 리뷰 MD | `docs/operator_closeout/phase52_webhook_auth_routing_review.md` |
| 런타임 헬스 표면 리뷰 MD | `docs/operator_closeout/phase52_runtime_health_surface_review.md` |

## 저장소 기록 실측 (2026-04-14 — 권위 번들)

| 필드 | 값 |
|------|-----|
| 번들 `generated_utc` | `2026-04-14T05:03:19.383370+00:00` |
| `ok` | `true` |
| `smoke_metrics_ok` | `true` |
| Phase 51 번들(앵커) | `docs/operator_closeout/phase51_external_trigger_ingest_bundle.json` |
| 등록 소스 수 | `3` (`phase52_direct`, `phase52_queue`, `phase52_rate`) |
| 인증 실패 기록 | `auth_failures_recorded` ≥ 1 (잘못된 비밀) |
| 라우팅 거절 | `disallowed_raw_rejected` ≥ 1 (허용되지 않은 raw 타입) |
| 레이트리밋 | `rate_limited_events` ≥ 1 (`phase52_rate`, 분당 1건) |
| 큐 | `queued_events` 1, `flush_registry_ok` true, `pending_after_flush` 0 |
| Phase 48 `phase48_generated_utc` | `2026-04-14T05:03:19.382446+00:00` |
| 사이클 ID | `81395afa-235b-4598-952d-52b973a49358` |
| 감사 `why_cycle_started` | `phase52_governed_webhook_smoke` |
| supplemental 수 | `3` (`external_supplemental_count`) |
| 잡 | 생성 3 · 실행 3 (`debate.execute`) |
| `runtime_health_summary.health_status` | `healthy` |
| `external_source_activity_v52` (번들 발췌) | `null` — 스모크는 `phase52_external_smoke_*` 격리 경로; 헬스 병합은 기본 `external_source_registry_v1.json` 기준(리뷰 MD 노트) |
| Phase 53 권고 | `signed_payload_hmac_source_rotation_and_dead_letter_replay_v1` |

## Cockpit·API

- `POST /api/runtime/external-ingest/authenticated` — 헤더 `X-Source-Id`, `X-Webhook-Secret`, 본문 ≤ 32768 bytes
- 기존 `POST /api/runtime/external-ingest` — Phase 52 게이트 없음(레거시/MVP 경로)

## Related

`docs/phase52_patch_report.md`, `docs/operator_closeout/phase52_closeout.md`, `docs/phase51_evidence.md`, `HANDOFF.md`
