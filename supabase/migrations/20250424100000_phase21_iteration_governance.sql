-- Phase 21: iteration governance audit fields + single open slot per program/universe/policy.

alter table public.public_repair_iteration_series
  add column if not exists governance_audit_json jsonb not null default '{}'::jsonb;

comment on column public.public_repair_iteration_series.governance_audit_json is
  'Phase 21: pause/closure reasons, resume history, last incompatibility (JSON).';

-- At most one non-closed (active or paused) series per (program, universe, policy).
create unique index if not exists public_repair_iteration_series_one_open_per_key
  on public.public_repair_iteration_series (program_id, universe_name, policy_version)
  where status in ('active', 'paused');
