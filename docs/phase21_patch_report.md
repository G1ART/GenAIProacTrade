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

- Single commit message: `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`. 짧은 SHA는 `git rev-parse --short HEAD`로 확인.

## Golden path CLI

- `advance-public-repair-series --program-id latest --universe U --out path/stem`

## Production boundary

- `state_change.runner` must not reference `public_repair_iteration` or `public_repair_campaign` (see tests).
