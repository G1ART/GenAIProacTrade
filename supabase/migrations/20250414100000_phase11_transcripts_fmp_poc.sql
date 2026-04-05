-- Phase 11: single-vendor (FMP) earnings call transcript PoC — no truth-spine merge

insert into public.data_source_registry (
  source_id, provider_name, source_name, source_class, asset_domain, data_family,
  point_in_time_safety, license_or_rights_scope, cost_tier, activation_status,
  notes_json, provenance_policy_json
) values (
  'fmp_earning_call_transcripts_poc',
  'Financial Modeling Prep',
  'Earnings call transcript API (PoC binding)',
  'premium',
  'equities',
  'transcripts',
  'event_date_vs_fmp_publish_timestamp_explicit',
  'FMP_subscription_terms_apply_redistribution_per_license',
  'paid_tier_required',
  'inactive',
  '{"phase11_poc":true,"env":"FMP_API_KEY"}'::jsonb,
  '{"downstream_label":"premium_overlay","provider_binding":"fmp_v3_earning_call_transcript"}'::jsonb
)
on conflict (source_id) do update set
  provider_name = excluded.provider_name,
  source_name = excluded.source_name,
  notes_json = excluded.notes_json,
  provenance_policy_json = excluded.provenance_policy_json,
  updated_at = now();

update public.source_overlay_availability
set
  linked_source_id = 'fmp_earning_call_transcripts_poc',
  metadata_json = coalesce(metadata_json, '{}'::jsonb)
    || '{"phase11_provider":"financial_modeling_prep","binding":"fmp_earning_call_transcript_v3"}'::jsonb,
  updated_at = now()
where overlay_key = 'earnings_call_transcripts';

create table if not exists public.transcript_ingest_runs (
  id uuid primary key default gen_random_uuid(),
  provider_code text not null,
  operation text not null,
  probe_status text,
  status text not null,
  detail_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table public.transcript_ingest_runs is
  'Transcript PoC ingest/probe audit; does not alter SEC/XBRL spine.';

create table if not exists public.raw_transcript_payloads_fmp (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  fiscal_year int not null,
  fiscal_quarter int not null,
  http_status int,
  raw_response_json jsonb not null,
  fetched_at timestamptz not null default now(),
  ingest_run_id uuid references public.transcript_ingest_runs (id) on delete set null,
  unique (symbol, fiscal_year, fiscal_quarter)
);

create table if not exists public.normalized_transcripts (
  id uuid primary key default gen_random_uuid(),
  provider_name text not null,
  source_registry_id text references public.data_source_registry (source_id) on delete restrict,
  issuer_id uuid references public.issuer_master (id) on delete set null,
  ticker text not null,
  event_date date,
  fiscal_period text not null,
  published_at timestamptz,
  available_at timestamptz,
  ingested_at timestamptz not null default now(),
  revision_id text,
  transcript_text text,
  source_rights_class text not null default 'premium',
  provenance_json jsonb not null default '{}'::jsonb,
  normalization_status text not null,
  raw_payload_fmp_id uuid references public.raw_transcript_payloads_fmp (id) on delete set null,
  created_at timestamptz not null default now(),
  unique (provider_name, ticker, fiscal_period)
);

create index if not exists normalized_transcripts_ticker_idx
  on public.normalized_transcripts (ticker, event_date desc nulls last);

comment on table public.normalized_transcripts is
  'PIT-aware normalized transcript rows; optional enrichment only for downstream messaging.';

alter table public.daily_watchlist_entries
  add column if not exists transcript_enrichment_json jsonb not null default '{}'::jsonb;

comment on column public.daily_watchlist_entries.transcript_enrichment_json is
  'Phase 11: whether normalized transcript was used + metadata; never required for ranking.';
