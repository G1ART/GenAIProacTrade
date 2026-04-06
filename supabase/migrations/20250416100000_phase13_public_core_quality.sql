-- Phase 13: public-core cycle quality evidence + residual triage columns on casebook

create table if not exists public.public_core_cycle_quality_runs (
  id uuid primary key default gen_random_uuid(),
  state_change_run_id uuid not null references public.state_change_runs (id) on delete cascade,
  universe_name text not null,
  cycle_finished_ok boolean not null,
  quality_class text not null
    check (
      quality_class in (
        'strong',
        'usable_with_gaps',
        'thin_input',
        'degraded',
        'failed'
      )
    ),
  metrics_json jsonb not null default '{}'::jsonb,
  gap_reasons_ranked jsonb not null default '[]'::jsonb,
  overlay_status_json jsonb not null default '{}'::jsonb,
  residual_triage_json jsonb not null default '{}'::jsonb,
  unresolved_residual_items jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_core_cycle_quality_runs_created_idx
  on public.public_core_cycle_quality_runs (created_at desc);

create index if not exists public_core_cycle_quality_runs_state_change_idx
  on public.public_core_cycle_quality_runs (state_change_run_id, created_at desc);

comment on table public.public_core_cycle_quality_runs is
  'Deterministic quality gate for public-core cycles; reproducible metrics and triage summaries.';

alter table public.outlier_casebook_entries
  add column if not exists residual_triage_bucket text,
  add column if not exists premium_overlay_suggestion text;

alter table public.outlier_casebook_entries
  drop constraint if exists outlier_casebook_entries_residual_triage_bucket_check;

alter table public.outlier_casebook_entries
  add constraint outlier_casebook_entries_residual_triage_bucket_check check (
    residual_triage_bucket is null
    or residual_triage_bucket in (
      'data_missingness_dominated',
      'regime_mismatch',
      'delayed_market_recognition',
      'likely_exogenous_event',
      'contradictory_public_signal',
      'unresolved_residual'
    )
  );

comment on column public.outlier_casebook_entries.residual_triage_bucket is
  'Phase 13 triage taxonomy (research-oriented; not causal claims).';

comment on column public.outlier_casebook_entries.premium_overlay_suggestion is
  'Optional premium seam hint for later ROI; does not affect deterministic core.';
