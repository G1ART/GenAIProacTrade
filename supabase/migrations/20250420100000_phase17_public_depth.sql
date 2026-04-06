-- Phase 17: Public substrate depth expansion evidence (coverage, uplift, readiness).
-- Research/diagnostics only; no product scoring wiring.

create table if not exists public.public_depth_runs (
  id uuid primary key default gen_random_uuid(),
  universe_name text not null,
  policy_version text not null,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  expansion_summary_json jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists public_depth_runs_universe_idx
  on public.public_depth_runs (universe_name, created_at desc);

comment on table public.public_depth_runs is
  'Phase 17 bounded public-depth expansion orchestration; before/after evidence.';

create table if not exists public.public_depth_coverage_reports (
  id uuid primary key default gen_random_uuid(),
  public_depth_run_id uuid references public.public_depth_runs (id) on delete cascade,
  universe_name text not null,
  snapshot_label text not null
    check (snapshot_label in ('before', 'after', 'standalone')),
  metrics_json jsonb not null default '{}'::jsonb,
  exclusion_distribution_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_depth_coverage_reports_run_idx
  on public.public_depth_coverage_reports (public_depth_run_id);

create index if not exists public_depth_coverage_reports_universe_idx
  on public.public_depth_coverage_reports (universe_name, created_at desc);

comment on table public.public_depth_coverage_reports is
  'Deterministic substrate coverage snapshot for a universe (PIT join counts, quality shares).';

create table if not exists public.public_depth_uplift_reports (
  id uuid primary key default gen_random_uuid(),
  before_report_id uuid not null references public.public_depth_coverage_reports (id) on delete restrict,
  after_report_id uuid not null references public.public_depth_coverage_reports (id) on delete restrict,
  uplift_metrics_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_depth_uplift_reports_before_idx
  on public.public_depth_uplift_reports (before_report_id);

comment on table public.public_depth_uplift_reports is
  'Before vs after coverage metrics delta for public substrate depth campaigns.';
