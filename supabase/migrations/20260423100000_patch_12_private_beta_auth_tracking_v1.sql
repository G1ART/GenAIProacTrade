-- Patch 12 — Private Beta: Invite-Only Auth + Account-Level Usage Tracking
-- =====================================================================
-- Adds three tables (beta_users_v1, profiles_v1, product_usage_events_v1)
-- with RLS, the minimal indexes needed for per-user / per-event lookups,
-- and four admin-only views used by the /ops Beta Admin tab.
--
-- Safety:
--   * customer-accessed rows are locked down by RLS (users see only their
--     own row where relevant; events are service-role-only on purpose —
--     ingestion is server-mediated per Patch 12 §B3).
--   * all tables reference auth.users so a revoked supabase user cascades.
--   * idempotent: re-running the migration is a no-op.

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 1. beta_users_v1 — invite allowlist
-- ---------------------------------------------------------------------
create table if not exists public.beta_users_v1 (
    user_id       uuid primary key references auth.users(id) on delete cascade,
    email         text        not null unique,
    status        text        not null check (status in ('invited','active','paused','revoked')),
    role          text        not null check (role   in ('beta_user','admin','internal')),
    invited_at    timestamptz not null default now(),
    activated_at  timestamptz,
    notes         text
);

comment on table public.beta_users_v1 is
    'Patch 12 — invite-only beta allowlist. Service role manages rows; users can only SELECT their own row to know their status.';

create index if not exists beta_users_v1_status_idx
    on public.beta_users_v1 (status);

alter table public.beta_users_v1 enable row level security;

-- Users may read only their own row.
drop policy if exists beta_users_v1_select_own on public.beta_users_v1;
create policy beta_users_v1_select_own on public.beta_users_v1
    for select
    using (auth.uid() = user_id);

-- Write operations are restricted to service_role.
drop policy if exists beta_users_v1_service_all on public.beta_users_v1;
create policy beta_users_v1_service_all on public.beta_users_v1
    for all
    to service_role
    using (true)
    with check (true);

-- ---------------------------------------------------------------------
-- 2. profiles_v1 — minimal per-user profile (no PII beyond display_name)
-- ---------------------------------------------------------------------
create table if not exists public.profiles_v1 (
    user_id        uuid primary key references auth.users(id) on delete cascade,
    display_name   text,
    company        text,
    timezone       text,
    preferred_lang text check (preferred_lang in ('ko','en')),
    created_at     timestamptz not null default now(),
    last_seen_at   timestamptz
);

comment on table public.profiles_v1 is
    'Patch 12 — per-user product profile. Users may SELECT+UPDATE their own row; INSERT is performed by the server on first authentication.';

create index if not exists profiles_v1_last_seen_at_idx
    on public.profiles_v1 (last_seen_at desc nulls last);

alter table public.profiles_v1 enable row level security;

drop policy if exists profiles_v1_select_own on public.profiles_v1;
create policy profiles_v1_select_own on public.profiles_v1
    for select
    using (auth.uid() = user_id);

drop policy if exists profiles_v1_update_own on public.profiles_v1;
create policy profiles_v1_update_own on public.profiles_v1
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists profiles_v1_service_all on public.profiles_v1;
create policy profiles_v1_service_all on public.profiles_v1
    for all
    to service_role
    using (true)
    with check (true);

-- ---------------------------------------------------------------------
-- 3. product_usage_events_v1 — bounded account-level telemetry
-- ---------------------------------------------------------------------
create table if not exists public.product_usage_events_v1 (
    id           uuid primary key default gen_random_uuid(),
    occurred_at  timestamptz not null default now(),
    user_id      uuid        not null references auth.users(id) on delete cascade,
    session_id   uuid        not null,
    event_name   text        not null,
    surface      text        not null check (surface in ('today','research','replay','ask_ai','system','auth','admin')),
    route        text,
    asset_id     text,
    horizon_key  text        check (horizon_key in ('short','medium','medium_long','long')),
    result_state text,
    lang         text        check (lang in ('ko','en')),
    metadata     jsonb       not null default '{}'::jsonb
);

comment on table public.product_usage_events_v1 is
    'Patch 12 — bounded product telemetry. Server-mediated ingest only (RLS denies non-service roles). Event names must be on the Patch 12 §B2 allowlist (enforced in application code).';

create index if not exists product_usage_events_v1_user_occurred_idx
    on public.product_usage_events_v1 (user_id, occurred_at desc);

create index if not exists product_usage_events_v1_event_occurred_idx
    on public.product_usage_events_v1 (event_name, occurred_at desc);

create index if not exists product_usage_events_v1_session_idx
    on public.product_usage_events_v1 (session_id);

create index if not exists product_usage_events_v1_surface_occurred_idx
    on public.product_usage_events_v1 (surface, occurred_at desc);

alter table public.product_usage_events_v1 enable row level security;

-- SELECT and INSERT are service-role only. We deliberately do NOT expose
-- a customer-facing SELECT policy: the server reads aggregates on behalf
-- of admins, and customers never query their own raw events directly.
drop policy if exists product_usage_events_v1_service_all on public.product_usage_events_v1;
create policy product_usage_events_v1_service_all on public.product_usage_events_v1
    for all
    to service_role
    using (true)
    with check (true);

-- ---------------------------------------------------------------------
-- 4. Admin views — read-only aggregates (queried via service role).
-- ---------------------------------------------------------------------
create or replace view public.v_beta_users_active_v1 as
select status, role, count(*)::bigint as user_count
  from public.beta_users_v1
 group by status, role
 order by status, role;

comment on view public.v_beta_users_active_v1 is
    'Patch 12 — invited/active/paused/revoked counts, grouped by role.';

create or replace view public.v_beta_sessions_recent_v1 as
select
    user_id,
    session_id,
    count(*)::bigint                       as event_count,
    min(occurred_at)                       as session_started_at,
    max(occurred_at)                       as session_last_event_at,
    array_agg(distinct surface order by surface) as surfaces_touched
  from public.product_usage_events_v1
 where occurred_at >= now() - interval '24 hours'
 group by user_id, session_id
 order by session_last_event_at desc;

comment on view public.v_beta_sessions_recent_v1 is
    'Patch 12 — last 24h sessions with per-session event count and surface footprint.';

create or replace view public.v_beta_top_events_v1 as
select
    event_name,
    count(*)::bigint as event_count,
    count(distinct user_id)::bigint as unique_users,
    count(distinct session_id)::bigint as unique_sessions
  from public.product_usage_events_v1
 where occurred_at >= now() - interval '7 days'
 group by event_name
 order by event_count desc;

comment on view public.v_beta_top_events_v1 is
    'Patch 12 — last 7 days event counts, also reporting unique user/session cardinality.';

create or replace view public.v_beta_trust_signals_v1 as
with ask_totals as (
    select count(*)::bigint as total_ask_events
      from public.product_usage_events_v1
     where event_name in ('ask_quick_action_clicked','ask_free_text_submitted','ask_answer_rendered')
       and occurred_at >= now() - interval '7 days'
), ask_degraded as (
    select count(*)::bigint as degraded_count
      from public.product_usage_events_v1
     where event_name = 'ask_degraded_shown'
       and occurred_at >= now() - interval '7 days'
), sandbox_blocked as (
    select count(*)::bigint as blocked_count
      from public.product_usage_events_v1
     where event_name = 'sandbox_request_blocked'
       and occurred_at >= now() - interval '7 days'
), out_of_scope as (
    select count(*)::bigint as out_of_scope_count
      from public.product_usage_events_v1
     where event_name = 'ask_free_text_submitted'
       and coalesce(result_state, '') = 'out_of_scope'
       and occurred_at >= now() - interval '7 days'
)
select
    at.total_ask_events,
    ad.degraded_count,
    sb.blocked_count,
    os.out_of_scope_count,
    case when at.total_ask_events > 0
         then round(ad.degraded_count::numeric / at.total_ask_events, 4)
         else null end                              as ask_degraded_rate,
    case when at.total_ask_events > 0
         then round(os.out_of_scope_count::numeric / at.total_ask_events, 4)
         else null end                              as out_of_scope_rate
  from ask_totals at, ask_degraded ad, sandbox_blocked sb, out_of_scope os;

comment on view public.v_beta_trust_signals_v1 is
    'Patch 12 — last 7 days trust signal rollups (degraded ask rate / blocked sandbox count / out-of-scope ask rate).';

commit;
