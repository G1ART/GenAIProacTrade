-- Pragmatic Brain Absorption v1 — Milestone A (Real horizon closure)
-- Extends `factor_market_validation_panels` with long-horizon forward-return columns
-- so the Brain bundle builder can lift `medium_long` / `long` from template_fallback
-- to real_derived once the forward-return / validation pipeline is backfilled.
--
-- Compatibility: all columns are nullable. Existing panels produced before this
-- migration simply have NULL for the new columns and keep working.

alter table public.factor_market_validation_panels
  add column if not exists raw_return_6m numeric,
  add column if not exists excess_return_6m numeric,
  add column if not exists raw_return_1y numeric,
  add column if not exists excess_return_1y numeric;

comment on column public.factor_market_validation_panels.raw_return_6m is
  'forward return over ~126 trading days, joined from forward_returns_daily_horizons(horizon_type=next_half_year).';
comment on column public.factor_market_validation_panels.excess_return_6m is
  'excess forward return over ~126 trading days (annualized risk-free avg → period).';
comment on column public.factor_market_validation_panels.raw_return_1y is
  'forward return over ~252 trading days, joined from forward_returns_daily_horizons(horizon_type=next_year).';
comment on column public.factor_market_validation_panels.excess_return_1y is
  'excess forward return over ~252 trading days.';
