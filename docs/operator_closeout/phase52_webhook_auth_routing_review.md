# Phase 52 — Governed webhook auth, budgets, routing, optional queue

- **OK / metrics**: `True` / `smoke_metrics_ok=True`
- **Generated**: `2026-04-14T05:03:19.383370+00:00`
- **Phase 51 bundle (input anchor)**: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase51_external_trigger_ingest_bundle.json`

## Source registry

- **Sources registered**: 3

## Summaries

```json
{
  "auth_results_summary": {
    "auth_failures_recorded": 1,
    "expected_min": 1
  },
  "rate_limit_results_summary": {
    "rate_limited_events": 1,
    "expected_min": 1
  },
  "routing_results_summary": {
    "disallowed_raw_rejected": 1,
    "expected_min": 1
  },
  "queue_summary": {
    "queued_events": 1,
    "flush_registry_ok": true,
    "flush_registry_entry_status": "accepted",
    "pending_after_flush": 0
  }
}
```

## Runtime health (excerpt)

```json
{
  "health_status": "healthy",
  "external_ingest_counts": {
    "total_entries": 3,
    "accepted_pending": 0,
    "consumed": 3,
    "rejected": 0,
    "deduped": 0
  },
  "external_source_activity_v52": null
}
```

**Note — `external_source_activity_v52` is `null` here**: the smoke run seeds **`phase52_external_smoke_source_registry_v1.json`** (isolated paths under `data/research_runtime/`). `merge_phase52_into_summary` reads the **production default** `external_source_registry_v1.json`; when that file has no registered sources (or is absent), the merge skips and the bundle snapshot shows `null`. This is expected for the default smoke layout and does not contradict `smoke_metrics_ok`.

## Phase 53

- **`signed_payload_hmac_source_rotation_and_dead_letter_replay_v1`**
- HMAC-signed JSON bodies (not only shared secret), per-source signing key rotation, dead-letter replay UI, and optional async worker — still no substrate repair or trade execution.

## HTTP

- `POST /api/runtime/external-ingest/authenticated` — headers `X-Source-Id`, `X-Webhook-Secret` (TLS required in production).
- Legacy `POST /api/runtime/external-ingest` unchanged (no Phase 52 gates).

## Persistent files

- `data/research_runtime/external_source_registry_v1.json`
- `data/research_runtime/external_source_budget_state_v1.json`
- `data/research_runtime/external_event_queue_v1.json`
