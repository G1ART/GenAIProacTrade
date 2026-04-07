# Phase 21 — Iteration governance and selector completion

**Date:** 2026-04-07

## Migration

- Apply `supabase/migrations/20250424100000_phase21_iteration_governance.sql` (governance_audit_json + one open series per program/universe/policy for active/paused).

## Selectors

- `latest`, `latest-success`, `latest-for-program`, `latest-compatible` (needs series context; CLI resolves active series when possible).
- `from-latest-pair`: use `resolve-repair-campaign-pair` CLI or `resolve_repair_campaign_latest_pair`.
- `latest-active-series`: `resolve_iteration_series_id` for advance/override flows.

## Lifecycle CLI

- `pause-public-repair-series`, `resume-public-repair-series`, `close-public-repair-series`

## Tests

- `src/tests/test_phase21_iteration_governance.py`: three escalation branches, infra exclusion, resolver, runner boundary.
- Full suite: `pytest src/tests -q` — **263 passed** (local).

## Git (this workspace)

- **3d956e9ece1fbd5ecc9722dc16d3acc83c853a7f** (`3d956e9`) — `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`. 이후 amend 시 `git rev-parse HEAD`로 갱신.

## Linked Supabase (MCP 참고)

- MCP에 연결된 프로젝트 마이그레이션 목록은 로컬 파일명(`20250424100000_…`)과 다를 수 있음. **이 저장소의 Phase 21 DDL은 `supabase/migrations/20250424100000_phase21_iteration_governance.sql`을 대상 DB에 적용**하면 됨.

## Golden path CLI

- `advance-public-repair-series --program-id latest --universe U --out path/stem`

## Production boundary

- `state_change.runner` must not reference `public_repair_iteration` or `public_repair_campaign` (see tests).
