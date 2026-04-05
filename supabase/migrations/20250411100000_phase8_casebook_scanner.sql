-- Phase 8: Outlier Casebook + Daily Scanner (operational layer; no execution language)

create table if not exists public.outlier_casebook_runs (
  id uuid primary key default gen_random_uuid(),
  state_change_run_id uuid not null references public.state_change_runs (id) on delete cascade,
  universe_name text not null,
  detection_logic_version text not null default 'outlier_heuristic_v1',
  policy_json jsonb not null default '{}'::jsonb,
  entries_created integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists outlier_casebook_runs_run_idx
  on public.outlier_casebook_runs (state_change_run_id, created_at desc);

comment on table public.outlier_casebook_runs is
  'Batch metadata for outlier casebook generation; entries link here for audit.';

create table if not exists public.outlier_casebook_entries (
  id uuid primary key default gen_random_uuid(),
  casebook_run_id uuid not null references public.outlier_casebook_runs (id) on delete cascade,
  candidate_id uuid not null references public.state_change_candidates (id) on delete cascade,
  issuer_id uuid references public.issuer_master (id) on delete restrict,
  cik text not null,
  ticker text,
  company_name text,
  as_of_date date not null,
  memo_id uuid references public.investigation_memos (id) on delete set null,
  outlier_type text not null,
  outlier_severity numeric,
  primary_discrepancy_summary text not null,
  expected_pattern_summary text not null,
  observed_pattern_summary text not null,
  uncertainty_summary text not null,
  limitation_notes text not null default '',
  contamination_regime_missingness_json jsonb not null default '{}'::jsonb,
  source_trace jsonb not null default '{}'::jsonb,
  status text not null default 'open'
    check (status in ('open', 'reviewed', 'archived', 'suppressed')),
  is_heuristic boolean not null default true,
  message_short_title text not null,
  message_why_matters text not null,
  message_what_could_wrong text not null,
  message_unknown text not null,
  message_plain_language text not null,
  overlay_future_seams_json jsonb not null default '{"news":"not_available_yet","ownership":"not_available_yet","positioning":"not_available_yet","macro_regime_overlay":"not_available_yet"}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint outlier_casebook_entries_type_check check (
    outlier_type in (
      'reaction_gap',
      'persistence_failure',
      'contamination_override',
      'regime_mismatch',
      'thesis_challenge_divergence',
      'unexplained_residual'
    )
  )
);

create unique index if not exists outlier_casebook_entries_run_cand_type_uidx
  on public.outlier_casebook_entries (casebook_run_id, candidate_id, outlier_type);

create index if not exists outlier_casebook_entries_candidate_idx
  on public.outlier_casebook_entries (candidate_id);

create index if not exists outlier_casebook_entries_type_idx
  on public.outlier_casebook_entries (outlier_type, created_at desc);

comment on table public.outlier_casebook_entries is
  'Structured outlier memory: discrepancy + uncertainty + message-ready fields; heuristic types flagged.';

create table if not exists public.scanner_runs (
  id uuid primary key default gen_random_uuid(),
  as_of_calendar_date date not null,
  state_change_run_id uuid not null references public.state_change_runs (id) on delete cascade,
  universe_name text not null,
  policy_json jsonb not null default '{}'::jsonb,
  status text not null default 'completed',
  created_at timestamptz not null default now()
);

create index if not exists scanner_runs_date_idx
  on public.scanner_runs (as_of_calendar_date desc, universe_name);

comment on table public.scanner_runs is
  'Daily scanner execution record; low-noise policy in policy_json (top_n, filters).';

create table if not exists public.daily_signal_snapshots (
  id uuid primary key default gen_random_uuid(),
  scanner_run_id uuid not null unique references public.scanner_runs (id) on delete cascade,
  stats_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table public.daily_signal_snapshots is
  'Aggregate counts / class distribution for one scanner run (one row per run).';

create table if not exists public.daily_watchlist_entries (
  id uuid primary key default gen_random_uuid(),
  scanner_run_id uuid not null references public.scanner_runs (id) on delete cascade,
  candidate_id uuid not null references public.state_change_candidates (id) on delete cascade,
  priority_rank integer not null,
  priority_score numeric not null,
  deterministic_signal_summary text not null,
  thesis_summary text not null,
  challenge_summary text not null,
  uncertainty_summary text not null,
  reason_in_watchlist text not null,
  actionability_note text,
  regime_warning text,
  source_trace jsonb not null default '{}'::jsonb,
  message_short_title text not null,
  message_why_matters text not null,
  message_what_could_wrong text not null,
  message_unknown text not null,
  message_plain_language text not null,
  overlay_future_seams_json jsonb not null default '{"news":"not_available_yet","ownership":"not_available_yet","positioning":"not_available_yet","macro_regime_overlay":"not_available_yet"}'::jsonb,
  created_at timestamptz not null default now(),
  unique (scanner_run_id, candidate_id)
);

create index if not exists daily_watchlist_scanner_rank_idx
  on public.daily_watchlist_entries (scanner_run_id, priority_rank);

comment on table public.daily_watchlist_entries is
  'Bounded prioritized watchlist row with thesis+challenge+uncertainty + operator message fields.';
