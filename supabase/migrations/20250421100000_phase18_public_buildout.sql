-- Phase 18: Targeted public substrate build-out, exclusion actions, revalidation gate.

create table if not exists public.public_exclusion_action_reports (
  id uuid primary key default gen_random_uuid(),
  universe_name text not null,
  policy_version text not null,
  metrics_json jsonb not null default '{}'::jsonb,
  exclusion_distribution_json jsonb not null default '{}'::jsonb,
  action_queue_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_exclusion_action_reports_universe_idx
  on public.public_exclusion_action_reports (universe_name, created_at desc);

comment on table public.public_exclusion_action_reports is
  'Phase 18: dominant exclusion reasons mapped to symbols and suggested repair actions.';

create table if not exists public.public_buildout_runs (
  id uuid primary key default gen_random_uuid(),
  universe_name text not null,
  policy_version text not null,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  targeted_exclusions_json jsonb not null default '[]'::jsonb,
  attempted_actions_json jsonb not null default '[]'::jsonb,
  summary_json jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists public_buildout_runs_universe_idx
  on public.public_buildout_runs (universe_name, created_at desc);

comment on table public.public_buildout_runs is
  'Phase 18 bounded reason-aware build orchestration metadata.';

create table if not exists public.public_buildout_improvement_reports (
  id uuid primary key default gen_random_uuid(),
  public_buildout_run_id uuid references public.public_buildout_runs (id) on delete set null,
  before_metrics_json jsonb not null default '{}'::jsonb,
  after_metrics_json jsonb not null default '{}'::jsonb,
  exclusion_before_json jsonb not null default '{}'::jsonb,
  exclusion_after_json jsonb not null default '{}'::jsonb,
  improvement_summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_buildout_improvement_reports_run_idx
  on public.public_buildout_improvement_reports (public_buildout_run_id);

comment on table public.public_buildout_improvement_reports is
  'Before/after exclusion and substrate deltas for targeted build-out.';
