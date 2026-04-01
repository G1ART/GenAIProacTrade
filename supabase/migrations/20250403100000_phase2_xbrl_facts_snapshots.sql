-- Phase 2: XBRL facts raw/silver + issuer quarter snapshots

create table if not exists public.raw_xbrl_facts (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  accession_no text not null,
  dedupe_key text not null,
  taxonomy text,
  concept text not null,
  unit text,
  value_text text,
  value_numeric numeric,
  period_start date,
  period_end date,
  instant_date date,
  fiscal_year integer,
  fiscal_period text,
  filed_at timestamptz,
  accepted_at timestamptz,
  source_payload_json jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now()
);

create unique index if not exists raw_xbrl_facts_cik_accession_dedupe_uq
  on public.raw_xbrl_facts (cik, accession_no, dedupe_key);

comment on table public.raw_xbrl_facts is
  'XBRL fact 원형 보존. dedupe_key로 동일 fact 재삽입 방지. UPDATE 금지(앱 레벨 insert-only).';

create table if not exists public.silver_xbrl_facts (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  accession_no text not null,
  canonical_concept text not null,
  source_taxonomy text,
  source_concept text not null,
  unit text,
  numeric_value numeric,
  period_start date,
  period_end date,
  instant_date date,
  fact_type text not null,
  fiscal_year integer,
  fiscal_period text,
  revision_no integer not null default 1,
  fact_period_key text not null,
  normalized_summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists silver_xbrl_facts_cik_acc_canon_rev_period_uq
  on public.silver_xbrl_facts (
    cik,
    accession_no,
    canonical_concept,
    revision_no,
    fact_period_key
  );

comment on table public.silver_xbrl_facts is
  '정규화된 XBRL fact. canonical_concept + fact_period_key로 기간별 구분. revision_no로 규칙 변경 시 이력 확장.';

create table if not exists public.issuer_quarter_snapshots (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  fiscal_year integer not null,
  fiscal_period text not null,
  period_start timestamptz,
  period_end timestamptz,
  filed_at timestamptz,
  accepted_at timestamptz,
  accession_no text not null,
  revenue numeric,
  net_income numeric,
  operating_cash_flow numeric,
  total_assets numeric,
  total_liabilities numeric,
  cash_and_equivalents numeric,
  research_and_development numeric,
  capex numeric,
  gross_profit numeric,
  shares_outstanding numeric,
  snapshot_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists issuer_quarter_snapshots_identity_uq
  on public.issuer_quarter_snapshots (cik, fiscal_year, fiscal_period, accession_no);

comment on table public.issuer_quarter_snapshots is
  '공시(accession) + 회계 분기(fiscal_year, fiscal_period) 단위 스냅샷. 팩터 계산 전 factual 집계층.';
