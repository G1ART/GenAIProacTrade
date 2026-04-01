-- Phase 0: SEC filing 메타데이터 raw / silver 최소 스키마
-- 적용: Supabase SQL Editor 또는 supabase db push

create extension if not exists pgcrypto;

create table if not exists public.raw_sec_filings (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  company_name text not null,
  accession_no text not null,
  form text not null,
  filed_at timestamptz,
  accepted_at timestamptz,
  source_url text,
  payload_json jsonb not null,
  ingested_at timestamptz not null default now()
);

create unique index if not exists raw_sec_filings_cik_accession_uq
  on public.raw_sec_filings (cik, accession_no);

comment on table public.raw_sec_filings is
  'SEC 공시 메타데이터 원본(JSON). 동일 accession 재실행 시 insert 생략(앱 레벨 idempotency).';

create table if not exists public.silver_sec_filings (
  id uuid primary key default gen_random_uuid(),
  cik text not null,
  company_name text not null,
  accession_no text not null,
  form text not null,
  filed_at timestamptz,
  accepted_at timestamptz,
  normalized_summary_json jsonb not null,
  revision_no integer not null default 1,
  created_at timestamptz not null default now()
);

create unique index if not exists silver_sec_filings_cik_accession_rev_uq
  on public.silver_sec_filings (cik, accession_no, revision_no);

comment on table public.silver_sec_filings is
  '정규화 요약 레이어. revision_no로 수정 이력 확장 가능.';
