-- Deterministic universe backfill orchestration audit (no manual data entry)

create table if not exists public.backfill_orchestration_runs (
  id uuid primary key default gen_random_uuid(),
  mode text not null,
  universe_name text not null,
  requested_symbol_count integer,
  resolved_symbol_count integer,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  config_json jsonb not null default '{}'::jsonb,
  summary_json jsonb,
  error_json jsonb
);

create index if not exists backfill_orch_runs_started_idx
  on public.backfill_orchestration_runs (started_at desc);

comment on table public.backfill_orchestration_runs is
  'Full-universe backfill orchestration parent run; stages in backfill_stage_events.';

create table if not exists public.backfill_stage_events (
  id uuid primary key default gen_random_uuid(),
  orchestration_run_id uuid not null references public.backfill_orchestration_runs (id) on delete cascade,
  stage_name text not null,
  stage_status text not null,
  inserted_rows integer not null default 0,
  updated_rows integer not null default 0,
  skipped_rows integer not null default 0,
  warning_count integer not null default 0,
  error_count integer not null default 0,
  notes_json jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists backfill_stage_events_orch_idx
  on public.backfill_stage_events (orchestration_run_id);

comment on table public.backfill_stage_events is
  'Per-stage metrics for backfill-universe CLI; complements ingest_runs.';

-- Single-call coverage for report-backfill-status (service role / authenticated)
create or replace function public.backfill_coverage_counts()
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'issuer_master_rows', (select count(*)::bigint from public.issuer_master),
    'filing_index_rows', (select count(*)::bigint from public.filing_index),
    'raw_xbrl_facts_rows', (select count(*)::bigint from public.raw_xbrl_facts),
    'silver_xbrl_facts_rows', (select count(*)::bigint from public.silver_xbrl_facts),
    'issuer_quarter_snapshots_rows', (select count(*)::bigint from public.issuer_quarter_snapshots),
    'issuer_quarter_factor_panels_rows', (select count(*)::bigint from public.issuer_quarter_factor_panels),
    'forward_returns_daily_horizons_rows', (select count(*)::bigint from public.forward_returns_daily_horizons),
    'factor_market_validation_panels_rows', (select count(*)::bigint from public.factor_market_validation_panels),
    'state_change_candidates_rows', (select count(*)::bigint from public.state_change_candidates),
    'raw_xbrl_facts_distinct_cik', (select count(distinct cik)::bigint from public.raw_xbrl_facts),
    'silver_xbrl_facts_distinct_cik', (select count(distinct cik)::bigint from public.silver_xbrl_facts),
    'issuer_quarter_snapshots_distinct_cik', (select count(distinct cik)::bigint from public.issuer_quarter_snapshots),
    'issuer_quarter_factor_panels_distinct_cik', (select count(distinct cik)::bigint from public.issuer_quarter_factor_panels),
    'forward_returns_distinct_cik', (select count(distinct cik)::bigint from public.forward_returns_daily_horizons where cik is not null),
    'factor_market_validation_panels_distinct_cik', (select count(distinct cik)::bigint from public.factor_market_validation_panels),
    'state_change_candidates_distinct_cik', (select count(distinct cik)::bigint from public.state_change_candidates)
  );
$$;

grant execute on function public.backfill_coverage_counts() to authenticated;
grant execute on function public.backfill_coverage_counts() to service_role;
