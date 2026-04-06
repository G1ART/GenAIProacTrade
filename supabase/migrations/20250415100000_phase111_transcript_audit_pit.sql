-- Phase 11.1: append-only raw history for repeated FMP fetches (audit / revision trace)

create table if not exists public.raw_transcript_payloads_fmp_history (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  fiscal_year int not null,
  fiscal_quarter int not null,
  http_status int,
  raw_response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  superseded_raw_payload_id uuid references public.raw_transcript_payloads_fmp (id) on delete set null,
  ingest_run_id uuid references public.transcript_ingest_runs (id) on delete set null
);

create index if not exists raw_transcript_payloads_fmp_history_sym_yq_idx
  on public.raw_transcript_payloads_fmp_history (symbol, fiscal_year, fiscal_quarter, fetched_at desc);

comment on table public.raw_transcript_payloads_fmp_history is
  'Prior raw snapshots before each upsert to raw_transcript_payloads_fmp; immutable audit trail.';
