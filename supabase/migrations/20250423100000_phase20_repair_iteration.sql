-- Phase 20: Public repair iteration series, trend members, escalation decisions.

create table if not exists public.public_repair_iteration_series (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.research_programs (id) on delete cascade,
  universe_name text not null,
  policy_version text not null,
  status text not null default 'active'
    check (status in ('active', 'closed', 'paused')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists public_repair_iteration_series_program_idx
  on public.public_repair_iteration_series (program_id, status, updated_at desc);

comment on table public.public_repair_iteration_series is
  'Phase 20: governed series of Phase 19 repair campaign runs per program.';

create table if not exists public.public_repair_iteration_members (
  id uuid primary key default gen_random_uuid(),
  series_id uuid not null references public.public_repair_iteration_series (id) on delete cascade,
  repair_campaign_run_id uuid not null references public.public_repair_campaign_runs (id) on delete cascade,
  sequence_number int not null,
  trend_snapshot_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (series_id, sequence_number),
  unique (repair_campaign_run_id)
);

create index if not exists public_repair_iteration_members_series_idx
  on public.public_repair_iteration_members (series_id, sequence_number asc);

comment on table public.public_repair_iteration_members is
  'Phase 20: one row per completed repair campaign run in a series, with trend snapshot.';

create table if not exists public.public_repair_escalation_decisions (
  id uuid primary key default gen_random_uuid(),
  series_id uuid not null references public.public_repair_iteration_series (id) on delete cascade,
  recommendation text not null
    check (
      recommendation in (
        'continue_public_depth',
        'hold_and_repeat_public_repair',
        'open_targeted_premium_discovery'
      )
    ),
  rationale text not null default '',
  plateau_metrics_json jsonb not null default '{}'::jsonb,
  counterfactual_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_repair_escalation_decisions_series_idx
  on public.public_repair_escalation_decisions (series_id, created_at desc);

comment on table public.public_repair_escalation_decisions is
  'Phase 20: program-level escalation gate after analyzing iteration history.';
