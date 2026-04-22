-- AGH v1 Patch 9 C·A1 — Retention archive tables + count RPC.
--
-- Closes CF-8·A from the Patch 8 Scale Readiness Note. The active
-- `agentic_harness_packets_v1` and `agentic_harness_queue_jobs_v1` tables
-- keep unbounded history, which makes /api/runtime/health and packet
-- listing linear-in-history. This migration introduces two ``*_archive``
-- tables (same shape + an ``archived_at_utc`` column) and an RPC that
-- reports the per-layer packet count without pulling the rows into
-- Python — the supabase_store wiring in C·A3 uses the RPC.
--
-- Archival is non-destructive by design: the archive_v1 Python helpers
-- (C·A2) copy rows into the archive table and only then delete from the
-- active table. The ``harness-retention-archive --dry-run`` path lets
-- the operator preview the set before any mutation.
--
-- All statements are idempotent.

create table if not exists public.agentic_harness_packets_v1_archive (
    packet_id               text primary key,
    packet_type             text not null,
    packet_schema_version   int  not null default 1,
    target_layer            text not null,
    created_by_agent        text not null,
    created_at_utc          timestamptz not null,
    target_scope            jsonb not null default '{}'::jsonb,
    provenance_refs         text[] not null default '{}',
    confidence              numeric(6, 4),
    blocking_reasons        text[] not null default '{}',
    expiry_or_recheck_rule  text not null default '',
    status                  text not null default 'proposed',
    payload                 jsonb not null default '{}'::jsonb,
    updated_at_utc          timestamptz not null,
    archived_at_utc         timestamptz not null default now()
);

create index if not exists agentic_harness_packets_v1_archive_created_at_desc_idx
    on public.agentic_harness_packets_v1_archive (created_at_utc desc);

create index if not exists agentic_harness_packets_v1_archive_archived_at_desc_idx
    on public.agentic_harness_packets_v1_archive (archived_at_utc desc);


create table if not exists public.agentic_harness_queue_jobs_v1_archive (
    job_id          text primary key,
    queue_class     text not null,
    packet_id       text not null,
    enqueued_at_utc timestamptz not null,
    not_before_utc  timestamptz not null,
    attempts        int  not null default 0,
    max_attempts    int  not null default 3,
    last_error      text not null default '',
    status          text not null default 'enqueued',
    worker_agent    text not null default '',
    result_json     jsonb,
    archived_at_utc timestamptz not null default now()
);

create index if not exists agentic_harness_queue_jobs_v1_archive_enqueued_at_desc_idx
    on public.agentic_harness_queue_jobs_v1_archive (enqueued_at_utc desc);

create index if not exists agentic_harness_queue_jobs_v1_archive_archived_at_desc_idx
    on public.agentic_harness_queue_jobs_v1_archive (archived_at_utc desc);


-- AGH v1 Patch 9 C·A3 — Packet-count RPC.
-- Replaces the Python-side fetch-all-rows-and-count pattern that
-- supabase_store.count_packets_by_layer() previously used. The function
-- returns a JSONB object with ``{ total: int, by_layer: {...} }``. It
-- is a pure read + intentionally not security-definer; RLS applies.
create or replace function public.agentic_harness_count_packets_by_layer_v1()
returns jsonb
language sql
stable
as $$
    with counts as (
        select target_layer, count(*)::int as n
        from public.agentic_harness_packets_v1
        group by target_layer
    )
    select jsonb_build_object(
        'total', (select count(*)::int from public.agentic_harness_packets_v1),
        'by_layer', coalesce(
            (select jsonb_object_agg(target_layer, n) from counts),
            '{}'::jsonb
        )
    );
$$;

comment on function public.agentic_harness_count_packets_by_layer_v1() is
    'AGH v1 Patch 9 C·A3 — per-layer packet counts without pulling rows into Python.';

comment on table public.agentic_harness_packets_v1_archive is
    'AGH v1 Patch 9 C·A — retention archive target for aged packets. Append-only.';
comment on table public.agentic_harness_queue_jobs_v1_archive is
    'AGH v1 Patch 9 C·A — retention archive target for aged queue jobs. Append-only.';
