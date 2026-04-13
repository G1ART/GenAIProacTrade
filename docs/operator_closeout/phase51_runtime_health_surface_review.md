# Phase 51 — Runtime health surface (cockpit)

- **Bundle ref**: `phase51_external_trigger_ingest_bundle.json` (`generated_utc`: 2026-04-13T06:30:40.611318+00:00)

## Founder-facing preview (API shape)

- **headline**: 런타임 상태가 정상으로 보입니다.
- **subtext**: 최근 감사 요약과 외부 트리거 적재 상태를 아래에서 확인할 수 있습니다.

### Plain lines

- 마지막 감사 시각: 2026-04-13T06:30:40.610800+00:00
- 마지막 사이클 건너뜀: 아니오
- 외부 트리거 적재: 총 1건 · 승인 대기 0 · 소비됨 1 · 거절 0 · 중복 제거 0

### Recent skips (plain)

- (none)

## API

- `GET /api/runtime/health` — human-first card + `advanced` machine block
