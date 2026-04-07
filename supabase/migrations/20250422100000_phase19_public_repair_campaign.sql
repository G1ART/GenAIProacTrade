-- Phase 19: Closed-loop public repair campaign + research revalidation evidence.

create table if not exists public.public_repair_campaign_runs (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.research_programs (id) on delete cascade,
  universe_name text not null,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  baseline_coverage_report_id uuid references public.public_depth_coverage_reports (id) on delete set null,
  baseline_exclusion_action_report_id uuid references public.public_exclusion_action_reports (id) on delete set null,
  baseline_campaign_run_id uuid references public.validation_campaign_runs (id) on delete set null,
  baseline_validation_snapshot_json jsonb not null default '{}'::jsonb,
  baseline_campaign_recommendation text,
  targeted_buildout_run_id uuid references public.public_buildout_runs (id) on delete set null,
  after_coverage_report_id uuid references public.public_depth_coverage_reports (id) on delete set null,
  improvement_report_id uuid references public.public_buildout_improvement_reports (id) on delete set null,
  reran_phase15 boolean not null default false,
  reran_phase16 boolean not null default false,
  rerun_skip_reason_json jsonb not null default '{}'::jsonb,
  after_campaign_run_id uuid references public.validation_campaign_runs (id) on delete set null,
  final_decision text
    check (
      final_decision is null
      or final_decision in (
        'continue_public_depth',
        'consider_targeted_premium_seam',
        'repair_insufficient_repeat_buildout'
      )
    ),
  rationale_json jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists public_repair_campaign_runs_program_idx
  on public.public_repair_campaign_runs (program_id, created_at desc);

comment on table public.public_repair_campaign_runs is
  'Phase 19: one closed loop baseline → build-out → improvement → gated Phase15/16 → decision.';

create table if not exists public.public_repair_campaign_steps (
  id uuid primary key default gen_random_uuid(),
  repair_campaign_run_id uuid not null references public.public_repair_campaign_runs (id) on delete cascade,
  step_name text not null,
  status text not null
    check (status in ('pending', 'running', 'completed', 'skipped', 'failed')),
  detail_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_repair_campaign_steps_run_idx
  on public.public_repair_campaign_steps (repair_campaign_run_id, created_at asc);

comment on table public.public_repair_campaign_steps is
  'Phase 19: auditable step trace for repair campaigns.';

create table if not exists public.public_repair_revalidation_comparisons (
  id uuid primary key default gen_random_uuid(),
  repair_campaign_run_id uuid not null references public.public_repair_campaign_runs (id) on delete cascade,
  before_survival_distribution_json jsonb not null default '{}'::jsonb,
  after_survival_distribution_json jsonb not null default '{}'::jsonb,
  before_campaign_recommendation text,
  after_campaign_recommendation text,
  improvement_interpretation_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists public_repair_revalidation_comparisons_run_uidx
  on public.public_repair_revalidation_comparisons (repair_campaign_run_id);

comment on table public.public_repair_revalidation_comparisons is
  'Phase 19: durable before/after research outcomes for a repair campaign run.';

create table if not exists public.public_repair_campaign_decisions (
  id uuid primary key default gen_random_uuid(),
  repair_campaign_run_id uuid not null references public.public_repair_campaign_runs (id) on delete cascade,
  decision text not null
    check (
      decision in (
        'continue_public_depth',
        'consider_targeted_premium_seam',
        'repair_insufficient_repeat_buildout'
      )
    ),
  policy_version text not null,
  rationale_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists public_repair_campaign_decisions_run_idx
  on public.public_repair_campaign_decisions (repair_campaign_run_id, created_at desc);

comment on table public.public_repair_campaign_decisions is
  'Phase 19: machine-readable final branch decision for a repair campaign.';
