-- Phase 14: Research engine kernel (programs, hypotheses, reviews, referee, residual links)
-- Does not wire into deterministic scoring or watchlist ranking.

create table if not exists public.research_programs (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  research_question text not null,
  horizon_type text not null default 'next_quarter'
    check (horizon_type in ('next_month', 'next_quarter')),
  universe_name text not null,
  status text not null default 'draft'
    check (status in ('draft', 'active', 'completed', 'archived')),
  owner_actor text not null default 'operator',
  program_constraints_json jsonb not null default '{}'::jsonb,
  linked_quality_context_json jsonb not null default '{}'::jsonb,
  premium_overlays_allowed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists research_programs_status_idx
  on public.research_programs (status, created_at desc);

comment on table public.research_programs is
  'Phase 14 research program shell; isolated from product scoring path.';

create table if not exists public.research_hypotheses (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references public.research_programs (id) on delete cascade,
  hypothesis_title text not null,
  economic_rationale text not null,
  mechanism_json jsonb not null default '{}'::jsonb,
  feature_definition_json jsonb not null default '{}'::jsonb,
  scope_limits_json jsonb not null default '{}'::jsonb,
  expected_effect_json jsonb not null default '{}'::jsonb,
  failure_modes_json jsonb not null default '{}'::jsonb,
  status text not null default 'proposed'
    check (
      status in (
        'proposed',
        'under_review',
        'killed',
        'sandboxed',
        'candidate_recipe'
      )
    ),
  review_rounds_completed integer not null default 0
    check (review_rounds_completed >= 0 and review_rounds_completed <= 2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists research_hypotheses_program_idx
  on public.research_hypotheses (program_id, created_at desc);

comment on table public.research_hypotheses is
  'Structured research hypotheses with economic rationale; Phase 14 forge output.';

create table if not exists public.research_reviews (
  id uuid primary key default gen_random_uuid(),
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  reviewer_lens text not null
    check (
      reviewer_lens in (
        'mechanism',
        'pit_data',
        'residual',
        'compression'
      )
    ),
  round_number integer not null check (round_number >= 1 and round_number <= 2),
  decision text not null check (decision in ('pass', 'concern', 'reject')),
  strongest_objection text not null default '',
  evidence_needed text not null default '',
  proceed_to_validation boolean not null default false,
  review_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists research_reviews_hypothesis_idx
  on public.research_reviews (hypothesis_id, round_number, reviewer_lens);

comment on table public.research_reviews is
  'Bounded adversarial review lenses; max 2 rounds per hypothesis via application logic.';

create table if not exists public.research_referee_decisions (
  id uuid primary key default gen_random_uuid(),
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  final_decision text not null
    check (final_decision in ('kill', 'sandbox', 'candidate_recipe')),
  rationale text not null,
  disagreement_json jsonb not null default '{}'::jsonb,
  next_step_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists research_referee_hypothesis_idx
  on public.research_referee_decisions (hypothesis_id, created_at desc);

comment on table public.research_referee_decisions is
  'Forced kill/sandbox/candidate_recipe after bounded review; preserves disagreement JSON.';

create table if not exists public.research_residual_links (
  id uuid primary key default gen_random_uuid(),
  hypothesis_id uuid not null references public.research_hypotheses (id) on delete cascade,
  outlier_casebook_entry_id uuid,
  residual_triage_bucket text,
  unresolved_reason text,
  premium_overlay_hint text,
  claims_to_explain text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists research_residual_links_hypothesis_idx
  on public.research_residual_links (hypothesis_id);

comment on table public.research_residual_links is
  'Links hypotheses to residual triage / casebook; informational premium hints only.';
