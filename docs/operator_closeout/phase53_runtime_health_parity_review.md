# Phase 53 — Runtime health parity (smoke vs prod paths)

`build_runtime_health_summary` accepts optional overrides for external source registry, budget, queue, dead-letter, and replay-guard paths so **external_source_activity_v52** and **external_ingress_phase53** merge from the same files the smoke wrote.

## Legacy ingest

```json
{
  "path": "POST /api/runtime/external-ingest",
  "allowed": false,
  "note": "Unauthenticated legacy path; disabled by default (control plane)."
}
```

## external_source_activity_v52 (excerpt)

```json
{
  "sources": [
    {
      "source_id": "s53_signed",
      "source_name": "signed_smoke",
      "enabled": true,
      "queue_mode": "direct",
      "active_signing_key_id": "k_active_v1",
      "outcome_counts": {
        "accepted_registry": 1,
        "rejected_signature": 2,
        "registry_other": 1,
        "rejected_replay": 1
      },
      "recent_auth_failures_tail": [
        {
          "timestamp": "2026-04-14T05:45:34.136675+00:00",
          "reason": "bad_signature"
        },
        {
          "timestamp": "2026-04-14T05:45:34.137104+00:00",
          "reason": "stale_timestamp"
        }
      ],
      "recent_rate_limits_tail": [],
      "recent_routing_rejections_tail": []
    }
  ],
  "queue_depth_pending": 0,
  "registry_configured": true,
  "registry_path": "/Users/hyunminkim/GenAIProacTrade/data/research_runtime/phase53_smoke_source_registry_v1.json"
}
```

## external_ingress_phase53

```json
{
  "signed_ingress_configured": true,
  "sources_with_rotation_keys": 1,
  "dead_letter_total_entries": 3,
  "dead_letter_by_failure_stage": {
    "signature": 2,
    "replay_guard": 1
  },
  "replay_guard_active_entries": 2,
  "registry_path_used": "/Users/hyunminkim/GenAIProacTrade/data/research_runtime/phase53_smoke_source_registry_v1.json"
}
```
