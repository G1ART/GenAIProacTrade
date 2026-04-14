# Phase 52 — Runtime health surface (source + queue visibility)

- **Bundle phase**: `phase52_webhook_auth_routing`
- **Generated**: `2026-04-14T05:03:19.383370+00:00`

## Health status

- `healthy`

## External ingest counts (registry)

```json
{
  "total_entries": 3,
  "accepted_pending": 0,
  "consumed": 3,
  "rejected": 0,
  "deduped": 0
}
```

## Phase 52 per-source activity (`external_source_activity_v52`)

```json
null
```

**Why `null`**: per-source / queue lines are merged from **`data/research_runtime/external_source_registry_v1.json`** (production default). The Phase 52 smoke uses **`phase52_external_smoke_*`** files instead, so the health merge often leaves `external_source_activity_v52` unset in the written summary — ingest counts above still reflect the smoke ingest registry.

## Cockpit preview (human lines)

```json
[
  "마지막 감사 시각: 2026-04-14T05:03:19.382786+00:00",
  "마지막 사이클 건너뜀: 아니오",
  "외부 트리거 적재: 총 3건 · 승인 대기 0 · 소비됨 3 · 거절 0 · 중복 제거 0"
]
```
