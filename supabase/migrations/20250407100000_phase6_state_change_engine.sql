-- Phase 6: deterministic issuer-date state change engine (no execution / no forward-return features)

create table if not exists public.state_change_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null,
  universe_name text not null,
  as_of_date_start date,
  as_of_date_end date,
  factor_version text not null,
  config_version text not null,
  input_snapshot_json jsonb not null default '{}'::jsonb,
  row_count integer not null default 0,
  warning_count integer not null default 0,
  status text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  error_json jsonb
);

create index if not exists state_change_runs_started_at_idx
  on public.state_change_runs (started_at desc);

comment on table public.state_change_runs is
  'Phase 6 state change 실행 메타. forward return / validation label 을 입력으로 사용하지 않음.';

create table if not exists public.issuer_state_change_components (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.state_change_runs (id) on delete cascade,
  issuer_id uuid references public.issuer_master (id) on delete restrict,
  cik text not null,
  ticker text,
  as_of_date date not null,
  universe_name text not null,
  signal_family text not null,
  signal_name text not null,
  current_value numeric,
  lag_1_value numeric,
  lag_2_value numeric,
  lag_4_value numeric,
  level_score numeric,
  velocity_score numeric,
  acceleration_score numeric,
  persistence_score numeric,
  contamination_score numeric,
  regime_fit_score numeric,
  coverage_ratio numeric not null default 1.0,
  quality_flags_json jsonb not null default '{}'::jsonb,
  notes_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists issuer_state_change_components_uq
  on public.issuer_state_change_components (run_id, cik, as_of_date, signal_name);

create index if not exists issuer_state_change_components_run_idx
  on public.issuer_state_change_components (run_id);

comment on table public.issuer_state_change_components is
  '신호·발행일 단위 long-form 구성요소. level/velocity/acceleration/persistence; contamination·regime_fit 은 nullable 허용.';

create table if not exists public.issuer_state_change_scores (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.state_change_runs (id) on delete cascade,
  issuer_id uuid references public.issuer_master (id) on delete restrict,
  cik text not null,
  ticker text,
  as_of_date date not null,
  universe_name text not null,
  state_change_score_v1 numeric not null,
  state_change_direction text not null,
  confidence_band text not null,
  included_component_count integer not null default 0,
  missing_component_count integer not null default 0,
  normalized_weight_sum numeric,
  gating_status text not null,
  top_driver_signals_json jsonb not null default '[]'::jsonb,
  warnings_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists issuer_state_change_scores_uq
  on public.issuer_state_change_scores (run_id, cik, as_of_date);

create index if not exists issuer_state_change_scores_run_idx
  on public.issuer_state_change_scores (run_id);

comment on table public.issuer_state_change_scores is
  '발행일 단위 투명 합성 점수. 정보 누락은 중립과 동일 취급하지 않음(missing_component_count 등).';

create table if not exists public.state_change_candidates (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.state_change_runs (id) on delete cascade,
  issuer_id uuid references public.issuer_master (id) on delete restrict,
  cik text not null,
  ticker text,
  as_of_date date not null,
  candidate_rank integer not null,
  candidate_class text not null,
  candidate_reason_json jsonb not null default '{}'::jsonb,
  dominant_change_type text,
  confidence_band text not null,
  human_review_priority integer not null default 0,
  excluded_reason text,
  created_at timestamptz not null default now()
);

create unique index if not exists state_change_candidates_uq
  on public.state_change_candidates (run_id, cik, as_of_date, candidate_rank);

create index if not exists state_change_candidates_run_idx
  on public.state_change_candidates (run_id);

comment on table public.state_change_candidates is
  '후속 조사 후보(실행 신호 아님). candidate_class: investigate_now|investigate_watch|recheck_later|insufficient_data|excluded.';
