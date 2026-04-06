-- Phase 15: Research Validation Lab — recipe validation runs, metrics, comparisons, survival, failures.
-- Research lane only; no product scoring or watchlist wiring.

create table if not exists public.recipe_validation_runs (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.research_programs (id) on delete cascade,
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  recipe_candidate_status_at_start text not null,
  baseline_config_json jsonb not null default '{}'::jsonb,
  cohort_config_json jsonb not null default '{}'::jsonb,
  window_config_json jsonb not null default '{}'::jsonb,
  quality_filter_json jsonb not null default '{}'::jsonb,
  linked_state_change_run_id uuid references public.state_change_runs (id) on delete set null,
  linked_public_core_quality_run_id uuid references public.public_core_cycle_quality_runs (id) on delete set null,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists recipe_validation_runs_hypothesis_idx
  on public.recipe_validation_runs (hypothesis_id, created_at desc);

create index if not exists recipe_validation_runs_program_idx
  on public.recipe_validation_runs (program_id, created_at desc);

comment on table public.recipe_validation_runs is
  'Phase 15 validation lab run: baselines, cohorts, windows, quality filters; research only.';

create table if not exists public.recipe_validation_results (
  id uuid primary key default gen_random_uuid(),
  validation_run_id uuid not null references public.recipe_validation_runs (id) on delete cascade,
  metric_name text not null,
  metric_value numeric,
  cohort_key text not null default 'pooled',
  baseline_name text not null default '',
  result_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists recipe_validation_results_run_idx
  on public.recipe_validation_results (validation_run_id, cohort_key);

comment on table public.recipe_validation_results is
  'Deterministic validation metrics per cohort/window/baseline slice.';

create table if not exists public.recipe_validation_comparisons (
  id uuid primary key default gen_random_uuid(),
  validation_run_id uuid not null references public.recipe_validation_runs (id) on delete cascade,
  comparison_type text not null,
  baseline_name text not null,
  candidate_delta_json jsonb not null default '{}'::jsonb,
  interpretation_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists recipe_validation_comparisons_run_idx
  on public.recipe_validation_comparisons (validation_run_id);

comment on table public.recipe_validation_comparisons is
  'Recipe vs explicit baseline deltas; deterministic interpretation JSON.';

create table if not exists public.recipe_survival_decisions (
  id uuid primary key default gen_random_uuid(),
  validation_run_id uuid not null references public.recipe_validation_runs (id) on delete cascade,
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  survival_status text not null
    check (
      survival_status in (
        'survives',
        'weak_survival',
        'demote_to_sandbox',
        'archive_failed'
      )
    ),
  rationale text not null,
  fragility_json jsonb not null default '{}'::jsonb,
  next_step_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists recipe_survival_decisions_run_idx
  on public.recipe_survival_decisions (validation_run_id);

create index if not exists recipe_survival_decisions_status_idx
  on public.recipe_survival_decisions (survival_status, created_at desc);

comment on table public.recipe_survival_decisions is
  'Deterministic survival outcome for a validation run; not product promotion.';

create table if not exists public.recipe_failure_cases (
  id uuid primary key default gen_random_uuid(),
  validation_run_id uuid not null references public.recipe_validation_runs (id) on delete cascade,
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  residual_link_id uuid references public.research_residual_links (id) on delete set null,
  failure_reason text not null,
  representative_context_json jsonb not null default '{}'::jsonb,
  premium_overlay_hint text,
  created_at timestamptz not null default now()
);

create index if not exists recipe_failure_cases_run_idx
  on public.recipe_failure_cases (validation_run_id);

comment on table public.recipe_failure_cases is
  'Structured failure memory: cohorts, contradictions, missing context hints.';
