-- Phase 4: market data layers, universe, forward returns, factor–market validation panel

-- 1) Universe memberships (sp500_current, sp500_proxy_candidates_v1, …)
create table if not exists public.universe_memberships (
  id uuid primary key default gen_random_uuid(),
  universe_name text not null,
  symbol text not null,
  cik text,
  as_of_date date not null,
  membership_status text not null,
  source_name text not null,
  source_payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists universe_memberships_uq
  on public.universe_memberships (universe_name, symbol, as_of_date);

create index if not exists universe_memberships_name_asof_idx
  on public.universe_memberships (universe_name, as_of_date desc);

comment on table public.universe_memberships is
  '지수/후보 유니버스 구성원. sp500_proxy_candidates_v1 은 공식 편입 후보가 아닌 MVP 프록시 후보군.';

-- 2) Market symbol registry (ticker ↔ CIK / 메타)
create table if not exists public.market_symbol_registry (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  cik text,
  company_name text,
  exchange text,
  currency text,
  asset_type text,
  is_active boolean not null default true,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  source_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists market_symbol_registry_symbol_uq
  on public.market_symbol_registry (symbol);

comment on table public.market_symbol_registry is
  '거래 심볼과 issuer(CIK) 연결. 자동 매핑 실패는 앱 레벨 quality_flags 로 기록.';

-- 3) Raw daily prices (provider payload 보존)
create table if not exists public.raw_market_prices_daily (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  trade_date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  adjusted_close numeric,
  volume numeric,
  source_name text not null,
  source_payload_json jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now()
);

create unique index if not exists raw_market_prices_daily_uq
  on public.raw_market_prices_daily (symbol, trade_date, source_name);

-- 4) Silver normalized daily prices (수익률 계산 기준)
create table if not exists public.silver_market_prices_daily (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  cik text,
  trade_date date not null,
  close numeric not null,
  adjusted_close numeric,
  volume numeric,
  daily_return numeric,
  is_trading_day boolean not null default true,
  normalization_notes_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists silver_market_prices_daily_uq
  on public.silver_market_prices_daily (symbol, trade_date);

create index if not exists silver_market_prices_daily_symbol_date_idx
  on public.silver_market_prices_daily (symbol, trade_date desc);

-- 5) Market metadata (MVP: latest-style snapshot per symbol/source)
create table if not exists public.market_metadata_latest (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  cik text,
  as_of_date date not null,
  market_cap numeric,
  shares_outstanding numeric,
  avg_daily_volume numeric,
  exchange text,
  sector text,
  industry text,
  source_name text not null,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists market_metadata_latest_uq
  on public.market_metadata_latest (symbol, source_name);

-- 6) Risk-free rates (daily, annualized % — 소스 README 참고)
create table if not exists public.risk_free_rates_daily (
  id uuid primary key default gen_random_uuid(),
  rate_date date not null,
  annualized_rate numeric not null,
  source_name text not null,
  source_payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists risk_free_rates_daily_uq
  on public.risk_free_rates_daily (rate_date, source_name);

-- 7) Forward returns (1m / 1q 등)
create table if not exists public.forward_returns_daily_horizons (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  cik text,
  signal_date date not null,
  horizon_type text not null,
  start_trade_date date not null,
  end_trade_date date not null,
  raw_forward_return numeric,
  excess_forward_return numeric,
  return_basis_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists forward_returns_horizons_uq
  on public.forward_returns_daily_horizons (symbol, signal_date, horizon_type);

create index if not exists forward_returns_symbol_signal_idx
  on public.forward_returns_daily_horizons (symbol, signal_date);

comment on table public.forward_returns_daily_horizons is
  '시그널일(공시 후 보수적 다음 거래일) 기준 선행 raw / excess 수익률. horizon_type: next_month | next_quarter.';

-- 8) Factor ↔ market validation panel
create table if not exists public.factor_market_validation_panels (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  symbol text,
  accession_no text not null,
  fiscal_year integer not null,
  fiscal_period text not null,
  factor_version text not null,
  signal_available_date date,
  market_cap_asof numeric,
  liquidity_proxy_json jsonb not null default '{}'::jsonb,
  raw_return_1m numeric,
  excess_return_1m numeric,
  raw_return_1q numeric,
  excess_return_1q numeric,
  panel_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists factor_market_validation_panels_uq
  on public.factor_market_validation_panels (cik, accession_no, factor_version);

comment on table public.factor_market_validation_panels is
  'issuer_quarter_factor_panels + 시장 수익률/메타 시점 정렬. 랭킹·백테스트 없음(validation join만).';
