# Phase 47 — Founder cockpit runtime

- **Phase**: `phase47_founder_cockpit_runtime`
- **Generated**: `2026-04-13T00:24:13.690156+00:00`
- **Phase 46 input**: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json`

## Runtime

- **Entry**: `PYTHONPATH=src python3 src/phase47_runtime/app.py`
- **Views**: home_overview, cohort_detail_drilldown, alerts_panel, decision_log, governed_conversation

## Governed conversation

- **Contract version**: `1`
- **Intents**: decision_summary, information_layer, research_layer, why_closed, provenance, what_changed, what_unproven, message_layer, closeout_layer

## Ledger actions (UI)

- **Alert actions**: acknowledge, resolve, supersede, dismiss
- **Decision types**: buy, defer, dismiss_alert, hold, reopen_request, sell, watch

## Reload

```json
{
  "kind": "explicit_http_post_reload",
  "path": "/api/reload",
  "staleness": "GET /api/meta exposes bundle_stale vs phase46 bundle mtime"
}
```

## Deploy

```json
{
  "primary": "internal_https_reverse_proxy",
  "notes_path": "docs/operator_closeout/phase47_runtime_deploy_notes.md",
  "example_hosts": [
    "127.0.0.1 (dev)",
    "corp VPN static host behind nginx"
  ]
}
```

## Phase 48

- **선행 연구 단일 사이클 런타임**: 구현·**운영 클로즈 완료** — `docs/operator_closeout/phase48_closeout.md`, `run-phase48-proactive-research-runtime`. 다중 사이클: **Phase 49** `run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1` · `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`.
- **(메타 번들 스텁, 미구현)** `external_notification_connectors_and_runtime_audit_log_v1` — 외부 알림 커넥터·런타임 감사 로그; UI 트랙 **47b / 47c / …** 또는 후속 페이즈에서 별도 지시.
