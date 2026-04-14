# Phase 52 — 운영 클로즈아웃 (거버넌스 웹훅 인증·소스 예산·라우팅·선택 큐)

**상태**: **종료 (closed)** — 2026-04-14 UTC 기준 권위 번들 `generated_utc` **`2026-04-14T05:03:19.383370+00:00`**, `ok: true`, `smoke_metrics_ok: true`.

## 범위

- **구현**: `src/phase52_runtime/` — 소스 레지스트리, SHA-256 비밀 해시 검증, 분당·윈도 예산, 원시/정규화 트리거 화이트리스트, 경계 큐, `governed_ingress`, 스모크 오케스트레이터.
- **Phase 51 연동**: 기존 `process_external_payload` / 적재 레지스트리·감사·정규화 경로 유지; 인증 경로는 **`POST /api/runtime/external-ingest/authenticated`** + 헤더 `X-Source-Id`, `X-Webhook-Secret`.
- **Phase 47 연동**: `app.py`가 위 헤더를 `dispatch_json`에 전달.
- **런타임 헬스**: `phase51_runtime.runtime_health` 에서 `merge_phase52_into_summary` 호출 — 운영 기본 경로 `data/research_runtime/external_source_registry_v1.json` 에 **등록된 소스가 1개 이상**일 때 `external_source_activity_v52` 병합(스모크는 격리 파일을 쓰므로 번들 스냅샷에서는 `null` 일 수 있음).
- **비목표**: 광역 기판 수리, 프리미엄 구매 실행, 무인증 공개 웹훅, 자율 매매 공표.

## 수락 기준 (충족)

1. 소스 레지스트리 스키마 및 `shared_secret_hash`(SHA-256 hex) 저장 모델.
2. 잘못된/누락된 인증은 적재 소비 없이 감사(`phase52_auth_failure` 등)에 기록.
3. 소스별 `rate_limit_per_minute` / `max_events_per_window` 결정론적 거절 및 예산 상태 파일 갱신.
4. `allowed_raw_event_types` · `normalized_trigger_allowlist` 위반 시 라우팅 거절.
5. `queue_mode: enqueue_before_cycle` 시 큐 적재 → `flush_one_queued_event_to_registry` 로 적재 후 Phase 48 supplemental 과 합류; `dedupe_key` 중복 적재 방지.
6. **권위 스모크 비영**: 인증 실패·라우팅 거절·레이트리밋·큐+플러시·3건 supplemental → 잡 3 생성·3 실행·토론·디스커버리 등 비영.

## 실측 스냅샷 (권위 번들, 2026-04-14)

- **명령**: `PYTHONPATH=src python3 -m main run-phase52-governed-webhook-auth-routing-smoke --repo-root <repo>` (선택 `--persist-runtime-health`)
- **사이클 ID**: `81395afa-235b-4598-952d-52b973a49358` — 감사 `why_cycle_started`: **`phase52_governed_webhook_smoke`**
- **Supplemental**: 3건 (`manual_watchlist` / `debate.execute`, 소스 `phase52_rate`, `phase52_direct`, `phase52_queue` 경로의 dedupe 키 각 1건)
- **적재 레지스트리(스모크 격리)**: `consumed` 3, `external_ingest_counts.total_entries` 3
- **헬스**: `health_status` = `healthy`
- **요약 카운터**: `auth_failures_recorded` 1, `rate_limited_events` 1, `disallowed_raw_rejected` 1, 큐 `queued_events` 1 후 `pending_after_flush` 0

## 격리 산출 (스모크 실행 시)

- `data/research_runtime/phase52_external_smoke_source_registry_v1.json`
- `data/research_runtime/phase52_external_smoke_budget_v1.json`
- `data/research_runtime/phase52_external_smoke_queue_v1.json`
- `data/research_runtime/phase52_smoke_ingest_v1.json`, `phase52_smoke_audit_v1.json`, `phase52_smoke_*` (잡 레지스트리·디스커버리·수동 트리거 스텁 등)

운영 시 소스·예산·큐 기본 파일명은 번들 필드 `production_registry_paths_note` 참고.

## 후속 (Phase 52 밖)

- **Phase 53**: `signed_payload_hmac_source_rotation_and_dead_letter_replay_v1` — 번들 `phase53` 필드 참고.

## 참고

- 증거·체크리스트: **`docs/phase52_evidence.md`**
- 패치 보고: **`docs/phase52_patch_report.md`**
- 번들·리뷰: **`docs/operator_closeout/phase52_webhook_auth_routing_bundle.json`**, **`phase52_webhook_auth_routing_review.md`**, **`phase52_runtime_health_surface_review.md`**
- 핸드오프: **`HANDOFF.md`**
- 전 단계 클로즈: **`docs/operator_closeout/phase51_closeout.md`**
