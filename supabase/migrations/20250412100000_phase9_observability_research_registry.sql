-- Phase 9: operational observability + research registry hardening (no auto-promotion)

create table if not exists public.operational_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null,
  component text not null,
  linked_external_id uuid,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  duration_ms integer,
  status text not null
    check (status in ('running', 'success', 'warning', 'failed', 'empty_valid')),
  error_code text,
  error_class text,
  error_message_summary text,
  rows_read integer,
  rows_written integer,
  tokens_used integer,
  warnings_count integer not null default 0,
  metadata_json jsonb not null default '{}'::jsonb,
  trace_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists operational_runs_type_started_idx
  on public.operational_runs (run_type, started_at desc);

create index if not exists operational_runs_status_idx
  on public.operational_runs (status, started_at desc);

comment on table public.operational_runs is
  'Cross-component run audit: state_change, harness memo, casebook, scanner. tokens_used null if N/A.';

create table if not exists public.operational_failures (
  id uuid primary key default gen_random_uuid(),
  operational_run_id uuid not null references public.operational_runs (id) on delete cascade,
  failure_category text not null,
  detail text not null,
  created_at timestamptz not null default now(),
  constraint operational_failures_category_check check (
    failure_category in (
      'configuration_error',
      'db_migration_missing',
      'source_data_missing',
      'empty_but_valid',
      'heuristic_low_confidence',
      'execution_error',
      'other'
    )
  )
);

create index if not exists operational_failures_run_idx
  on public.operational_failures (operational_run_id);

comment on table public.operational_failures is
  'Queryable failure/warning facets; empty_but_valid distinguishes intentional zero-output.';

-- Harden hypothesis_registry (Phase 7 stub -> operational registry)
alter table public.hypothesis_registry
  add column if not exists title text;

update public.hypothesis_registry
set title = coalesce(nullif(trim(title), ''), '(legacy_stub)')
where title is null;

alter table public.hypothesis_registry
  alter column title set default '';

alter table public.hypothesis_registry
  alter column title set not null;

alter table public.hypothesis_registry
  add column if not exists research_item_status text not null default 'proposed';

alter table public.hypothesis_registry
  add column if not exists source_scope text not null default 'unspecified';

alter table public.hypothesis_registry
  add column if not exists intended_use text not null default 'unspecified';

alter table public.hypothesis_registry
  add column if not exists leakage_review_status text not null default 'not_reviewed';

alter table public.hypothesis_registry
  add column if not exists promotion_decision text not null default 'none';

alter table public.hypothesis_registry
  add column if not exists rejection_reason text;

alter table public.hypothesis_registry
  add column if not exists linked_artifacts jsonb not null default '[]'::jsonb;

alter table public.hypothesis_registry
  drop constraint if exists hypothesis_registry_research_item_status_check;

alter table public.hypothesis_registry
  add constraint hypothesis_registry_research_item_status_check check (
    research_item_status in (
      'proposed',
      'under_review',
      'blocked_leakage_risk',
      'sandbox_only',
      'approved_for_experiment',
      'rejected',
      'promoted_to_candidate_logic'
    )
  );

comment on table public.hypothesis_registry is
  'Research idea / factor proposal registry. Production scoring must NOT auto-read rows; promotion is explicit.';

-- promotion_gate_events: link to hypothesis + structured decision trail
alter table public.promotion_gate_events
  add column if not exists hypothesis_id uuid references public.hypothesis_registry (id) on delete set null;

alter table public.promotion_gate_events
  add column if not exists event_type text not null default 'review';

alter table public.promotion_gate_events
  add column if not exists decision_summary text;

alter table public.promotion_gate_events
  add column if not exists rationale text;

alter table public.promotion_gate_events
  add column if not exists actor text;

alter table public.promotion_gate_events
  add column if not exists metadata_json jsonb not null default '{}'::jsonb;

create index if not exists promotion_gate_events_hypothesis_idx
  on public.promotion_gate_events (hypothesis_id, created_at desc);

comment on table public.promotion_gate_events is
  'Promotion / rejection audit trail; does not mutate production scoring tables.';
