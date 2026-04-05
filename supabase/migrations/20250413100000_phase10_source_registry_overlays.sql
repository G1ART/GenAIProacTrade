-- Phase 10: source registry, rights/provenance scaffolding, premium overlay seams (no fake data)

-- --- Core registry ---
create table if not exists public.data_source_registry (
  source_id text primary key,
  provider_name text not null,
  source_name text not null,
  source_class text not null
    check (source_class in (
      'public', 'premium', 'proprietary', 'private_internal', 'partner_only'
    )),
  asset_domain text not null
    check (asset_domain in ('equities', 'crypto', 'property', 'multi')),
  data_family text not null
    check (data_family in (
      'filings', 'fundamentals', 'transcripts', 'estimates', 'prices',
      'options', 'ownership', 'news', 'alt', 'internal'
    )),
  point_in_time_safety text not null default 'documented_where_applicable',
  license_or_rights_scope text not null default 'see_rights_notes',
  cost_tier text not null default 'unknown',
  activation_status text not null default 'inactive'
    check (activation_status in ('active', 'inactive', 'planned', 'deprecated')),
  notes_json jsonb not null default '{}'::jsonb,
  provenance_policy_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.data_source_registry is
  'Authoritative catalog of data layers; public spine vs premium/proprietary/partner. No ingestion implied.';

create index if not exists data_source_registry_class_idx
  on public.data_source_registry (source_class, activation_status);

-- --- Access / entitlements / coverage / rights notes ---
create table if not exists public.source_access_profiles (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.data_source_registry (source_id) on delete cascade,
  profile_code text not null,
  access_mechanism text not null default 'unspecified',
  credential_required boolean not null default false,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (source_id, profile_code)
);

create table if not exists public.source_entitlements (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.data_source_registry (source_id) on delete cascade,
  entitlement_label text not null,
  status text not null default 'none'
    check (status in ('none', 'pending', 'active', 'revoked')),
  scope_description text,
  metadata_json jsonb not null default '{}'::jsonb,
  valid_from date,
  valid_to date,
  created_at timestamptz not null default now()
);

create table if not exists public.source_coverage_profiles (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.data_source_registry (source_id) on delete cascade,
  label text not null,
  coverage_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.source_rights_notes (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.data_source_registry (source_id) on delete cascade,
  note_kind text not null default 'general',
  body text not null,
  created_at timestamptz not null default now()
);

-- --- Overlay availability (separate from truth spine) ---
create table if not exists public.source_overlay_availability (
  overlay_key text primary key,
  linked_source_id text references public.data_source_registry (source_id) on delete set null,
  availability text not null default 'not_available_yet'
    check (availability in ('not_available_yet', 'partial', 'available')),
  last_checked_at timestamptz,
  metadata_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

comment on table public.source_overlay_availability is
  'Premium/proprietary overlay seam status; absence must stay explicit.';

-- --- Optional audit / gap report storage ---
create table if not exists public.source_overlay_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null default 'overlay_smoke_v1',
  status text not null default 'completed',
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.source_overlay_gap_reports (
  id uuid primary key default gen_random_uuid(),
  report_type text not null default 'roi_gap_v1',
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- --- Downstream: overlay awareness (does not replace overlay_future_seams_json) ---
alter table public.outlier_casebook_entries
  add column if not exists overlay_awareness_json jsonb not null default '{}'::jsonb;

comment on column public.outlier_casebook_entries.overlay_awareness_json is
  'Phase 10: which overlays exist/absent; truth spine remains public-first.';

alter table public.daily_watchlist_entries
  add column if not exists overlay_awareness_json jsonb not null default '{}'::jsonb;

comment on column public.daily_watchlist_entries.overlay_awareness_json is
  'Phase 10: overlay availability snapshot at row build time.';

-- --- Seed: mixed classes (idempotent upserts via delete+insert pattern simplified: use ON CONFLICT) ---
insert into public.data_source_registry (
  source_id, provider_name, source_name, source_class, asset_domain, data_family,
  point_in_time_safety, license_or_rights_scope, cost_tier, activation_status,
  notes_json, provenance_policy_json
) values
  (
    'sec_edgar_xbrl_public',
    'SEC',
    'EDGAR filings + XBRL (public)',
    'public',
    'equities',
    'filings',
    'accession_filed_at_and_accepted_at_rules',
    'US_public_filings_redistribution_subject_to_SEC_terms',
    'free_public',
    'active',
    '{"role":"deterministic_truth_spine_core","ingest_path":"existing_pipeline"}'::jsonb,
    '{"downstream_label":"public_truth_spine"}'::jsonb
  ),
  (
    'fred_dtb3_public',
    'FRED',
    'Risk-free daily (DTB3 graph CSV)',
    'public',
    'equities',
    'alt',
    'rate_date_calendar',
    'FRED_terms_apply',
    'free_public',
    'active',
    '{"role":"regime_input_public"}'::jsonb,
    '{"downstream_label":"public_truth_spine"}'::jsonb
  ),
  (
    'market_prices_yahoo_silver_eod',
    'Yahoo_chart',
    'Silver EOD prices (ingested)',
    'public',
    'equities',
    'prices',
    'trade_date_eod_only',
    'provider_terms_apply_non_professional_chart',
    'free_public',
    'active',
    '{"role":"market_join_public","quality_note":"chart_provider_not_bloomberg_class"}'::jsonb,
    '{"downstream_label":"public_truth_spine","quality_tier":"standard_eod"}'::jsonb
  ),
  (
    'earnings_call_transcripts_vendor_tbd',
    'TBD_VENDOR',
    'Earnings call transcripts (premium target)',
    'premium',
    'equities',
    'transcripts',
    'vendor_event_timestamp_and_revision_policy_tbd',
    'license_required_not_held',
    'paid_tier_unknown',
    'planned',
    '{"why_it_matters":"narrative_drift_vs_filings","mvp_scope":"read_only_normalized_chunks"}'::jsonb,
    '{"downstream_label":"premium_overlay","credentials":"not_available_yet"}'::jsonb
  ),
  (
    'analyst_estimates_vendor_tbd',
    'TBD_VENDOR',
    'Analyst consensus estimates (premium target)',
    'premium',
    'equities',
    'estimates',
    'fiscal_period_alignment_and_revision_semantics_tbd',
    'license_required_not_held',
    'paid_tier_unknown',
    'planned',
    '{"why_it_matters":"expectations_gap_vs_realized_fundamentals"}'::jsonb,
    '{"downstream_label":"premium_overlay","credentials":"not_available_yet"}'::jsonb
  ),
  (
    'higher_quality_price_intraday_vendor_tbd',
    'TBD_VENDOR',
    'Higher-quality price or intraday feed (premium target)',
    'proprietary',
    'equities',
    'prices',
    'vendor_pit_rules_tbd',
    'license_required_not_held',
    'paid_tier_unknown',
    'planned',
    '{"why_it_matters":"microstructure_and_open_close_quality"}'::jsonb,
    '{"downstream_label":"premium_overlay","credentials":"not_available_yet"}'::jsonb
  ),
  (
    'operator_internal_research_notes',
    'INTERNAL',
    'Operator private research notes (not a market feed)',
    'private_internal',
    'equities',
    'internal',
    'operator_authored_timestamps',
    'internal_use_only',
    'internal',
    'inactive',
    '{"placeholder":true,"must_not_mix_with_public_spine_rows":true}'::jsonb,
    '{"downstream_label":"private_internal"}'::jsonb
  ),
  (
    'partner_syndicated_feed_placeholder',
    'PARTNER_TBD',
    'Partner-only syndicated feed (placeholder)',
    'partner_only',
    'multi',
    'news',
    'partner_contract_tbd',
    'partner_agreement_required',
    'unknown',
    'inactive',
    '{"placeholder":true}'::jsonb,
    '{"downstream_label":"partner_only"}'::jsonb
  )
on conflict (source_id) do update set
  provider_name = excluded.provider_name,
  source_name = excluded.source_name,
  source_class = excluded.source_class,
  asset_domain = excluded.asset_domain,
  data_family = excluded.data_family,
  point_in_time_safety = excluded.point_in_time_safety,
  license_or_rights_scope = excluded.license_or_rights_scope,
  cost_tier = excluded.cost_tier,
  activation_status = excluded.activation_status,
  notes_json = excluded.notes_json,
  provenance_policy_json = excluded.provenance_policy_json,
  updated_at = now();

insert into public.source_access_profiles (source_id, profile_code, access_mechanism, credential_required, metadata_json)
values
  ('sec_edgar_xbrl_public', 'public_http', 'edgar_http', false, '{}'::jsonb),
  ('fred_dtb3_public', 'public_csv', 'fred_graph_csv', false, '{}'::jsonb),
  ('market_prices_yahoo_silver_eod', 'chart_provider', 'yahoo_chart', false, '{"rate_limits":"project_policy"}'::jsonb),
  ('earnings_call_transcripts_vendor_tbd', 'vendor_api', 'tbd', true, '{"status":"not_available_yet"}'::jsonb),
  ('analyst_estimates_vendor_tbd', 'vendor_api', 'tbd', true, '{"status":"not_available_yet"}'::jsonb)
on conflict (source_id, profile_code) do nothing;

delete from public.source_entitlements where source_id in (
  'sec_edgar_xbrl_public', 'earnings_call_transcripts_vendor_tbd', 'partner_syndicated_feed_placeholder'
);
insert into public.source_entitlements (source_id, entitlement_label, status, scope_description, metadata_json)
values
  ('sec_edgar_xbrl_public', 'public_read', 'active', 'US public filings', '{}'::jsonb),
  ('earnings_call_transcripts_vendor_tbd', 'commercial_license', 'none', 'not procured', '{"not_available_yet":true}'::jsonb),
  ('partner_syndicated_feed_placeholder', 'partner_mou', 'pending', 'no agreement on file', '{}'::jsonb);

delete from public.source_coverage_profiles where label in ('us_equities_broad', 'mvp_universe');
insert into public.source_coverage_profiles (source_id, label, coverage_json)
values
  ('sec_edgar_xbrl_public', 'us_equities_broad', '{"universe":"sp500_current_compatible","gaps":"foreign_private_issuers"}'::jsonb),
  ('market_prices_yahoo_silver_eod', 'mvp_universe', '{"note":"symbol_registry_join_required"}'::jsonb);

delete from public.source_rights_notes where note_kind = 'phase10_seed';
insert into public.source_rights_notes (source_id, note_kind, body)
values
  ('sec_edgar_xbrl_public', 'phase10_seed', 'Public filings; do not attribute partner data to SEC path.'),
  ('earnings_call_transcripts_vendor_tbd', 'phase10_seed', 'No vendor credentials in repo; adapter seam is stub-only.');

insert into public.source_overlay_availability (overlay_key, linked_source_id, availability, metadata_json)
values
  ('earnings_call_transcripts', 'earnings_call_transcripts_vendor_tbd', 'not_available_yet',
   '{"why_it_matters":"narrative_context","affected_layers":["memo","casebook","scanner"]}'::jsonb),
  ('analyst_estimates', 'analyst_estimates_vendor_tbd', 'not_available_yet',
   '{"why_it_matters":"expectations_anchor","affected_layers":["memo","casebook","validation_panel"]}'::jsonb),
  ('higher_quality_price_or_intraday', 'higher_quality_price_intraday_vendor_tbd', 'not_available_yet',
   '{"why_it_matters":"execution_irrelevant_but_signal_timing_quality","affected_layers":["prices","scanner"]}'::jsonb),
  ('options_or_microstructure_overlay', null, 'not_available_yet',
   '{"optional_fourth":true,"affected_layers":["research_only"]}'::jsonb)
on conflict (overlay_key) do update set
  linked_source_id = excluded.linked_source_id,
  availability = excluded.availability,
  metadata_json = excluded.metadata_json,
  updated_at = now();
