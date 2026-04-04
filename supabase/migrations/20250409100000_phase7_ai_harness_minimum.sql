-- Phase 7: AI Harness Minimum / Message Layer Minimum (overlay only; no truth mutation)

create table if not exists public.ai_harness_candidate_inputs (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.state_change_candidates (id) on delete cascade,
  state_change_run_id uuid not null references public.state_change_runs (id) on delete cascade,
  contract_version text not null default 'ai_harness_input_v1',
  payload_json jsonb not null,
  payload_hash text not null,
  built_at timestamptz not null default now(),
  unique (candidate_id, contract_version)
);

create index if not exists ai_harness_inputs_run_idx
  on public.ai_harness_candidate_inputs (state_change_run_id);

comment on table public.ai_harness_candidate_inputs is
  'Deterministic JSON input contract for memo generation. Does not replace state_change_* truth.';

create table if not exists public.investigation_memos (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.state_change_candidates (id) on delete cascade,
  input_id uuid references public.ai_harness_candidate_inputs (id) on delete set null,
  memo_version integer not null default 1,
  generation_mode text not null,
  memo_json jsonb not null,
  referee_passed boolean not null default false,
  referee_flags_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  unique (candidate_id, memo_version)
);

create index if not exists investigation_memos_candidate_idx
  on public.investigation_memos (candidate_id);

comment on table public.investigation_memos is
  'Investigation memo overlay. thesis + challenge + synthesis + uncertainty; no execution language.';

create table if not exists public.investigation_memo_claims (
  id uuid primary key default gen_random_uuid(),
  memo_id uuid not null references public.investigation_memos (id) on delete cascade,
  claim_key text not null,
  claim_text text not null,
  uncertainty_label text not null
    check (uncertainty_label in ('confirmed', 'plausible_hypothesis', 'unverifiable')),
  evidence_ref_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists investigation_memo_claims_memo_idx
  on public.investigation_memo_claims (memo_id);

create table if not exists public.operator_review_queue (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null unique references public.state_change_candidates (id) on delete cascade,
  issuer_id uuid references public.issuer_master (id) on delete restrict,
  cik text not null,
  as_of_date date not null,
  status text not null
    check (status in ('pending', 'reviewed', 'needs_followup', 'blocked_insufficient_data')),
  memo_id uuid references public.investigation_memos (id) on delete set null,
  notes text,
  updated_at timestamptz not null default now()
);

create index if not exists operator_review_queue_status_idx
  on public.operator_review_queue (status, as_of_date desc);

comment on table public.operator_review_queue is
  'Operator review queue; primary key candidate_id. No trading workflow.';

-- Stubs for future R&D / promotion separation (no production wiring)
create table if not exists public.hypothesis_registry (
  id uuid primary key default gen_random_uuid(),
  stub_status text not null default 'reserved',
  notes_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table public.hypothesis_registry is
  'Phase 7 stub: future research-lab hypotheses; not wired to scoring.';

create table if not exists public.promotion_gate_events (
  id uuid primary key default gen_random_uuid(),
  stub_status text not null default 'reserved',
  notes_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table public.promotion_gate_events is
  'Phase 7 stub: future promotion gates; discovery must not auto-promote.';
