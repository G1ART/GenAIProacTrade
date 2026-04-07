# Phase 23 — Operator-grade post-patch closeout (one command, zero-UUID golden path)

**Date:** 2026-04-07

## Intent

Replace manual post-patch chains (SQL dir hunting, JSON `active_series_id` copy/paste, ad-hoc advance vs depth choice) with a **single orchestrated closeout**, preserving **auditability** (internal UUIDs still written to artifacts) and **no premium auto-open**.

## New / changed CLI

| Command | Role |
|---------|------|
| `run-post-patch-closeout --universe U` | Migration report → phase17–22 smokes → resolve/create series → deterministic chooser → optional advance → depth series brief export → `docs/operator_closeout/latest_closeout_summary.md` |
| `report-required-migrations` | Local `supabase/migrations/*.sql` vs `supabase_migrations.schema_migrations` when API-visible; `--write-bundle` emits concatenated SQL |
| `verify-db-phase-state` | Ordered REST smokes (same chain as `scripts/operator_post_patch_smokes.sh` phase17–22) |
| `export-public-depth-series-brief` | **Operator mode:** omit `--series-id`; require `--program-id` + `--universe` — uses `resolve_iteration_series_for_operator` |

## Deterministic chooser

`choose_post_patch_next_action_from_signals` / `choose_post_patch_next_action`:

- `verify_only` — `--verify-only` on closeout
- `hold_for_plateau_review` — escalation `open_targeted_premium_discovery` (human review, no auto advance) **or** `public_depth_near_plateau_review_required`
- `advance_public_depth_iteration` — `continue_public_depth_buildout`
- `advance_repair_series` — `repeat_targeted_public_repair`
- Default fallback — `advance_public_depth_iteration` (**public-first** safe default)

## Evidence (examples)

### 0) Production-style closeout (실측, 2026-04-07)

- **Command:** `run-post-patch-closeout --universe sp500_current` (with `PYTHONPATH=src`).
- **Migration API probe:** `False` — PostgREST `PGRST106` (`Invalid schema: supabase_migrations`; API에 `public`/`graphql_public` 만 노출). **정상적인 Supabase 구성에서 흔함.**
- **Schema truth:** phase17–22 **smokes all passed** → 클로즈아웃은 계속 진행·완료.
- **Series:** resolved `active_compatible_series`; audit `series_id` recorded in `docs/operator_closeout/latest_closeout_summary.md` (operator did not paste UUID).
- **Chooser / action:** `advance_repair_series` (`repeat_targeted_public_repair` / `hold_and_repeat_public_repair`) — **success True**; artifacts under `docs/operator_closeout/closeout_advance_repair.*`, `closeout_depth_series_brief.*`.
- **상세 증거 메모:** `docs/phase23_evidence.md`.

### 1) One-command closeout (다른 런에서 나올 수 있는 stdout 형태)

`schema_migrations` 가 API에 열려 있으면 `migration_report_ok=True` 가 될 수 있다. 열리지 않으면 경고 한 줄 후 스모크로 진행.

```
[run-post-patch-closeout] migration_probe_ok=False   # e.g. PGRST106
[run-post-patch-closeout] phase_smokes_ok=True
[run-post-patch-closeout] series_resolved_rule=active_compatible_series
[run-post-patch-closeout] chooser_action=advance_public_depth_iteration   # 또는 advance_repair_series
[run-post-patch-closeout] OK summary -> docs/operator_closeout/latest_closeout_summary.md
```

### 2) No UUID on golden path

`run-post-patch-closeout --universe U` accepts **no** series UUID.  
`export-public-depth-series-brief --program-id latest --universe U --out ...` likewise.

### 3) Migration preflight

```bash
python3 src/main.py report-required-migrations
```

If `applied_probe_ok: false`, closeout **still proceeds** after a one-line warning; **schema truth** is `verify-db-phase-state` / closeout’s embedded smoke chain. If probe succeeds and versions are missing, closeout **fails** and can write `bundle_pending_migrations.sql`.

### 4) Founder-readable artifact

Path: `docs/operator_closeout/latest_closeout_summary.md` — answers migrations probe, smokes, internal series id (audit), action taken, success, next step, public-first line.

### 5) Chooser tests

`src/tests/test_phase23_operator_closeout.py` — parametrized `choose_post_patch_next_action_from_signals`, migration/bundle/smoke-chain, guided error strings(ambiguous universe/series), CLI 등록, runner 경계.

전체 회귀: `PYTHONPATH=src pytest src/tests -q` → **309 passed** (Phase 24 포함, 환경 기준).

### 6) Production scoring boundary

`test_runner_still_no_public_repair_iteration_reference` in the same file (and Phase 22 test) — `state_change.runner` must not reference `public_repair_iteration` / `public_repair_campaign`.

## Presets

- Default file: `.operator_closeout_preset.json` (git-optional), schema in `docs/operator_closeout_preset.example.json`
- `run-post-patch-closeout --use-default-preset`

## Non-negotiables (verified in code policy)

- No automatic premium live integration; `open_targeted_premium_discovery` → **hold**, not advance.
- Infra quarantine defaults unchanged (plateau collection / Phase 21–22 paths).
- PIT / research vs production scoring separation unchanged.

## Docs / handoff

- `docs/OPERATOR_POST_PATCH.md` — **≤3 steps** normal flow + debug appendix
- `HANDOFF.md` — Phase 23 section at top
- `docs/phase23_evidence.md` — 운영 실측 스냅샷, **추가 필수 액션 여부**, 재현 명령
