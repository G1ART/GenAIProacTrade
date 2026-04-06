-- Phase 16: Validation campaign orchestrator — program-scale aggregation, decision gate.
-- Research lane only; no product scoring wiring.

alter table public.recipe_validation_runs
  add column if not exists join_policy_version text;

comment on column public.recipe_validation_runs.join_policy_version is
  'Canonical Phase 15 join rule for campaign reuse (e.g. cik_asof_v1: CIK norm + as_of<=signal).';

-- Existing completed runs: treat as current canonical join (post–Phase-15-fix deployments).
update public.recipe_validation_runs
set join_policy_version = 'cik_asof_v1'
where join_policy_version is null
  and status = 'completed';

create table if not exists public.validation_campaign_runs (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.research_programs (id) on delete cascade,
  policy_version text not null,
  run_mode text not null
    check (run_mode in ('reuse_only', 'reuse_or_run', 'force_rerun')),
  hypothesis_selection_json jsonb not null default '{}'::jsonb,
  aggregate_metrics_json jsonb not null default '{}'::jsonb,
  recommendation text not null
    check (
      recommendation in (
        'public_data_depth_first',
        'targeted_premium_seam_first',
        'insufficient_evidence_repeat_campaign'
      )
    ),
  rationale_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists validation_campaign_runs_program_idx
  on public.validation_campaign_runs (program_id, created_at desc);

comment on table public.validation_campaign_runs is
  'Phase 16 campaign: aggregate validation evidence and strategic recommendation.';

create table if not exists public.validation_campaign_members (
  id uuid primary key default gen_random_uuid(),
  campaign_run_id uuid not null references public.validation_campaign_runs (id) on delete cascade,
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  validation_run_id uuid not null references public.recipe_validation_runs (id) on delete restrict,
  survival_status text not null
    check (
      survival_status in (
        'survives',
        'weak_survival',
        'demote_to_sandbox',
        'archive_failed'
      )
    ),
  baseline_summary_json jsonb not null default '{}'::jsonb,
  fragility_summary_json jsonb not null default '{}'::jsonb,
  premium_hint_summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists validation_campaign_members_campaign_idx
  on public.validation_campaign_members (campaign_run_id);

create index if not exists validation_campaign_members_hypothesis_idx
  on public.validation_campaign_members (hypothesis_id);

comment on table public.validation_campaign_members is
  'Per-hypothesis validation snapshot used in a campaign aggregate.';

create table if not exists public.validation_campaign_decisions (
  id uuid primary key default gen_random_uuid(),
  campaign_run_id uuid not null references public.validation_campaign_runs (id) on delete cascade,
  recommendation text not null
    check (
      recommendation in (
        'public_data_depth_first',
        'targeted_premium_seam_first',
        'insufficient_evidence_repeat_campaign'
      )
    ),
  rationale text not null,
  evidence_thresholds_json jsonb not null default '{}'::jsonb,
  counterfactual_next_step_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists validation_campaign_decisions_campaign_idx
  on public.validation_campaign_decisions (campaign_run_id);

comment on table public.validation_campaign_decisions is
  'Machine-readable decision row with thresholds and counterfactual guidance.';
