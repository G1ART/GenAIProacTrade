-- Phase 5: deterministic factor validation / cross-sectional research layer (no backtest, no execution)

-- 1) Validation run audit
create table if not exists public.factor_validation_runs (
  id uuid primary key default gen_random_uuid(),
  run_type text not null default 'factor_validation_research',
  factor_version text not null,
  universe_name text not null,
  horizon_type text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'started',
  target_count integer,
  success_count integer not null default 0,
  failure_count integer not null default 0,
  metadata_json jsonb not null default '{}'::jsonb,
  error_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists factor_validation_runs_universe_horizon_idx
  on public.factor_validation_runs (universe_name, horizon_type, created_at desc);

comment on table public.factor_validation_runs is
  '팩터 검증 연구 실행 추적. 백테스트·전략·알파 점수 아님.';

-- 2) Factor × horizon × universe × return_basis summaries
create table if not exists public.factor_validation_summaries (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.factor_validation_runs (id) on delete cascade,
  factor_name text not null,
  factor_version text not null,
  universe_name text not null,
  horizon_type text not null,
  return_basis text not null check (return_basis in ('raw', 'excess')),
  sample_count integer not null default 0,
  valid_factor_count integer not null default 0,
  valid_return_count integer not null default 0,
  mean_factor numeric,
  std_factor numeric,
  mean_return numeric,
  std_return numeric,
  spearman_rank_corr numeric,
  pearson_corr numeric,
  hit_rate_same_sign numeric,
  summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (run_id, factor_name, horizon_type, universe_name, return_basis)
);

create index if not exists factor_validation_summaries_run_idx
  on public.factor_validation_summaries (run_id);

comment on table public.factor_validation_summaries is
  '연구용 기술통계·상관·부호일치율. 투자 추천·전략 수익 아님.';

-- 3) Quantile bucket descriptive stats (quintiles by default in app)
create table if not exists public.factor_quantile_results (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.factor_validation_runs (id) on delete cascade,
  factor_name text not null,
  factor_version text not null,
  universe_name text not null,
  horizon_type text not null,
  return_basis text not null check (return_basis in ('raw', 'excess')),
  quantile_index integer not null,
  quantile_count integer not null default 0,
  avg_factor_value numeric,
  avg_raw_return numeric,
  avg_excess_return numeric,
  median_raw_return numeric,
  median_excess_return numeric,
  result_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (run_id, factor_name, horizon_type, universe_name, quantile_index, return_basis)
);

create index if not exists factor_quantile_results_run_idx
  on public.factor_quantile_results (run_id);

comment on table public.factor_quantile_results is
  '팩터 분위별 기술적 평균·중앙값. 포트폴리오·롱숏 엔진 아님.';

-- 4) Coverage per factor within run slice
create table if not exists public.factor_coverage_reports (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.factor_validation_runs (id) on delete cascade,
  factor_name text not null,
  factor_version text not null,
  universe_name text not null,
  total_rows integer not null default 0,
  available_rows integer not null default 0,
  missing_rows integer not null default 0,
  missing_due_to_no_prior integer not null default 0,
  missing_due_to_zero_denominator integer not null default 0,
  missing_due_to_missing_fields integer not null default 0,
  coverage_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (run_id, factor_name, universe_name)
);

create index if not exists factor_coverage_reports_run_idx
  on public.factor_coverage_reports (run_id);

comment on table public.factor_coverage_reports is
  '검증 슬라이스 내 팩터 값 가용성. truth layer 미변경.';
