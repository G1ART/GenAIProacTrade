-- Phase 1: issuer master, filing identity index, ingest run audit

create table if not exists public.issuer_master (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  ticker text,
  company_name text not null,
  sic text,
  sic_description text,
  latest_known_exchange text,
  is_active boolean not null default true,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists issuer_master_cik_uq on public.issuer_master (cik);

comment on table public.issuer_master is
  'Issuer identity. CIK가 canonical key; ticker는 최근 관측값으로만 유지(유일 진실 아님).';

create table if not exists public.ingest_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null,
  target_count integer,
  success_count integer not null default 0,
  failure_count integer not null default 0,
  metadata_json jsonb not null default '{}'::jsonb,
  error_json jsonb
);

create index if not exists ingest_runs_started_at_idx on public.ingest_runs (started_at desc);

comment on table public.ingest_runs is
  '수집 실행 감사 로그. status: running | completed | failed';

create table if not exists public.filing_index (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  accession_no text not null,
  form text,
  filed_at timestamptz,
  accepted_at timestamptz,
  source_url text,
  filing_primary_document text,
  filing_description text,
  is_amendment boolean not null default false,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists filing_index_cik_accession_uq
  on public.filing_index (cik, accession_no);

comment on table public.filing_index is
  '공시 구조적 identity. raw는 원문 payload, silver는 해석층.';
