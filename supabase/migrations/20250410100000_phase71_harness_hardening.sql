-- Phase 7.1: claim-level traceability, rerun semantics, queue metadata

-- Memos: store input hash at generation time for idempotent reruns
alter table public.investigation_memos
  add column if not exists input_payload_hash text;

comment on column public.investigation_memos.input_payload_hash is
  'ai_harness_candidate_inputs.payload_hash snapshot; same hash + mode => in-place memo replace policy.';

create index if not exists investigation_memos_candidate_version_idx
  on public.investigation_memos (candidate_id, memo_version desc);

-- Review queue: operator semantics
alter table public.operator_review_queue
  add column if not exists status_reason text,
  add column if not exists reviewed_at timestamptz;

comment on column public.operator_review_queue.status_reason is
  'Human or CLI note for last status change (audit).';
comment on column public.operator_review_queue.reviewed_at is
  'Set when status becomes reviewed (optional audit).';

-- Claims: claim-level contract (Phase 7.1)
alter table public.investigation_memo_claims
  add column if not exists candidate_id uuid references public.state_change_candidates (id) on delete cascade;

update public.investigation_memo_claims c
set candidate_id = m.candidate_id
from public.investigation_memos m
where c.memo_id = m.id
  and c.candidate_id is null;

delete from public.investigation_memo_claims
where candidate_id is null;

alter table public.investigation_memo_claims
  alter column candidate_id set not null;

alter table public.investigation_memo_claims
  add column if not exists claim_id text;

update public.investigation_memo_claims
  set claim_id = claim_key
  where claim_id is null;

alter table public.investigation_memo_claims
  alter column claim_id set not null;

alter table public.investigation_memo_claims
  add column if not exists claim_role text;

update public.investigation_memo_claims
  set claim_role = case
    when claim_key = 'thesis' then 'thesis'
    when claim_key like 'challenge%' then 'challenge'
    else 'evidence'
  end
  where claim_role is null;

alter table public.investigation_memo_claims
  alter column claim_role set default 'evidence';

alter table public.investigation_memo_claims
  alter column claim_role set not null;

alter table public.investigation_memo_claims
  drop constraint if exists investigation_memo_claims_claim_role_check;

alter table public.investigation_memo_claims
  add constraint investigation_memo_claims_claim_role_check check (
    claim_role in ('thesis', 'challenge', 'synthesis', 'referee', 'evidence')
  );

alter table public.investigation_memo_claims
  add column if not exists statement text;

update public.investigation_memo_claims
  set statement = claim_text
  where statement is null;

alter table public.investigation_memo_claims
  alter column statement set not null;

alter table public.investigation_memo_claims
  add column if not exists support_summary text not null default '',
  add column if not exists counter_evidence_summary text not null default '',
  add column if not exists trace_refs jsonb not null default '{}'::jsonb,
  add column if not exists needs_verification boolean not null default false,
  add column if not exists verdict text not null default 'pending',
  add column if not exists claim_revision integer not null default 1,
  add column if not exists superseded_by uuid references public.investigation_memo_claims (id);

alter table public.investigation_memo_claims
  drop constraint if exists investigation_memo_claims_verdict_check;

alter table public.investigation_memo_claims
  add constraint investigation_memo_claims_verdict_check check (
    verdict in ('pending', 'accepted', 'rejected', 'review_required')
  );

create unique index if not exists investigation_memo_claims_memo_claim_id_uidx
  on public.investigation_memo_claims (memo_id, claim_id);

create index if not exists investigation_memo_claims_candidate_idx
  on public.investigation_memo_claims (candidate_id);

comment on table public.investigation_memo_claims is
  'Per-claim trace: role, statement, support/counter, uncertainty, trace_refs, verdict; replaces prior memo-only trace.';
