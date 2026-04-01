-- Phase 3: deterministic accounting factor panels (snapshot → factors)

create table if not exists public.issuer_quarter_factor_panels (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  fiscal_year integer not null,
  fiscal_period text not null,
  accession_no text not null,
  snapshot_id uuid references public.issuer_quarter_snapshots (id) on delete restrict,
  factor_version text not null default 'v1',
  accruals numeric,
  gross_profitability numeric,
  asset_growth numeric,
  capex_intensity numeric,
  rnd_intensity numeric,
  financial_strength_score numeric,
  factor_json jsonb not null default '{}'::jsonb,
  coverage_json jsonb not null default '{}'::jsonb,
  quality_flags_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists issuer_quarter_factor_panels_identity_uq
  on public.issuer_quarter_factor_panels (
    cik,
    fiscal_year,
    fiscal_period,
    accession_no,
    factor_version
  );

comment on table public.issuer_quarter_factor_panels is
  '회계 스냅샷 기반 결정적 팩터. 동일 (cik, fy, fp, accession, factor_version) 재실행 시 insert 생략(앱 레벨).';
