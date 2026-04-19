-- Agentic Operating Harness v1 - packet / queue / scheduler_ticks tables.
-- Creates three tables that the bounded operating harness in
-- `src/agentic_harness/` uses as its single packet contract store.
--
-- Hybrid design (plan q_infra_depth=C): Supabase is the persistent
-- packet/queue store; the scheduler that advances them remains an in-process
-- CLI tick (`python3 src/main.py harness-tick`). Real cron is Stage D and out
-- of scope for this patch.
--
-- All columns here are additive. Existing tables in the schema are untouched.

create table if not exists public.agentic_harness_packets_v1 (
    packet_id               text primary key,
    packet_type             text not null,
    packet_schema_version   int  not null default 1,
    target_layer            text not null,
    created_by_agent        text not null,
    created_at_utc          timestamptz not null default now(),
    target_scope            jsonb not null default '{}'::jsonb,
    provenance_refs         text[] not null default '{}',
    confidence              numeric(6, 4),
    blocking_reasons        text[] not null default '{}',
    expiry_or_recheck_rule  text not null default '',
    status                  text not null default 'proposed',
    payload                 jsonb not null default '{}'::jsonb,
    updated_at_utc          timestamptz not null default now(),

    constraint agentic_harness_packets_v1_target_layer_ck
        check (target_layer in (
            'layer1_ingest',
            'layer2_library',
            'layer3_research',
            'layer4_governance',
            'layer5_surface'
        )),
    constraint agentic_harness_packets_v1_status_ck
        check (status in (
            'proposed',
            'enqueued',
            'running',
            'done',
            'blocked',
            'escalated',
            'expired'
        )),
    constraint agentic_harness_packets_v1_packet_type_ck
        check (packet_type in (
            'IngestAlertPacketV1',
            'SourceArtifactPacketV1',
            'EventTriggerPacketV1',
            'LibraryIntegrityPacketV1',
            'CoverageGapPacketV1',
            'ResearchCandidatePacketV1',
            'OverlayProposalPacketV1',
            'EvaluationPacketV1',
            'PromotionGatePacketV1',
            'RegistryUpdateProposalV1',
            'ReplayLearningPacketV1',
            'UserQueryActionPacketV1'
        ))
);

create index if not exists agentic_harness_packets_v1_type_idx
    on public.agentic_harness_packets_v1 (packet_type);

create index if not exists agentic_harness_packets_v1_layer_status_idx
    on public.agentic_harness_packets_v1 (target_layer, status);

create index if not exists agentic_harness_packets_v1_created_at_desc_idx
    on public.agentic_harness_packets_v1 (created_at_utc desc);


create table if not exists public.agentic_harness_queue_jobs_v1 (
    job_id          text primary key,
    queue_class     text not null,
    packet_id       text not null references public.agentic_harness_packets_v1(packet_id)
                          on delete cascade,

    enqueued_at_utc timestamptz not null default now(),
    not_before_utc  timestamptz not null default now(),

    attempts        int  not null default 0 check (attempts >= 0 and attempts <= 99),
    max_attempts    int  not null default 3 check (max_attempts >= 1 and max_attempts <= 10),

    last_error      text not null default '',
    status          text not null default 'enqueued',
    worker_agent    text not null default '',

    result_json     jsonb,

    constraint agentic_harness_queue_jobs_v1_queue_class_ck
        check (queue_class in (
            'ingest_queue',
            'quality_queue',
            'research_queue',
            'governance_queue',
            'surface_action_queue',
            'replay_recompute_queue'
        )),
    constraint agentic_harness_queue_jobs_v1_status_ck
        check (status in ('enqueued', 'running', 'done', 'dlq', 'expired'))
);

-- Idempotency invariant: at most one enqueued|running job per (queue_class,
-- packet_id). Re-enqueue attempts for a packet that is already in-flight
-- collide on this partial unique index so the store layer can surface a
-- deterministic dedupe error.
create unique index if not exists
    agentic_harness_queue_jobs_v1_active_uniq
    on public.agentic_harness_queue_jobs_v1 (queue_class, packet_id)
    where status in ('enqueued', 'running');

create index if not exists agentic_harness_queue_jobs_v1_claimable_idx
    on public.agentic_harness_queue_jobs_v1 (queue_class, not_before_utc)
    where status = 'enqueued';


create table if not exists public.agentic_harness_scheduler_ticks_v1 (
    tick_id         uuid primary key default gen_random_uuid(),
    tick_at_utc     timestamptz not null default now(),
    tick_kind       text not null default 'harness_tick',
    summary         jsonb not null default '{}'::jsonb
);

create index if not exists agentic_harness_scheduler_ticks_v1_tick_at_desc_idx
    on public.agentic_harness_scheduler_ticks_v1 (tick_at_utc desc);


-- Comments for operators.
comment on table public.agentic_harness_packets_v1 is
    'Agentic Operating Harness v1: single packet contract store. Pydantic schemas in src/agentic_harness/contracts/packets_v1.py.';
comment on table public.agentic_harness_queue_jobs_v1 is
    'Agentic Operating Harness v1: six queue classes (ingest/quality/research/governance/surface_action/replay_recompute).';
comment on table public.agentic_harness_scheduler_ticks_v1 is
    'Agentic Operating Harness v1: append-only log of harness-tick invocations for observability.';
