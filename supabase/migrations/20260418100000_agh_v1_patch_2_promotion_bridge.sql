-- AGH v1 Patch 2: Promotion Bridge Closure (operator-gated registry patching).
--
-- Extends the Patch 0 (20260417120000_agentic_harness_v1.sql) CHECK constraints
-- so the agentic harness can persist the new audit packets and queue jobs
-- introduced in this patch:
--
--   * RegistryDecisionPacketV1        (approve | reject | defer audit record)
--   * RegistryPatchAppliedPacketV1    (before/after snapshot of the governed
--                                       horizon_provenance write)
--   * registry_apply_queue            (queue class consumed by
--                                       registry_patch_executor worker)
--   * packet status vocabulary gains applied | rejected | deferred for the
--     RegistryUpdateProposalV1 terminal states.
--
-- Non-goals (deliberate): no new tables, no RLS changes, no column additions.
-- Canonical registry writes still live in the brain bundle JSON
-- (data/mvp/metis_brain_bundle_v0.json) and are performed by the
-- registry_patch_executor worker, not by raw SQL. These check-constraint
-- extensions only let the harness audit store record the new packet taxonomy.

begin;

alter table public.agentic_harness_packets_v1
    drop constraint if exists agentic_harness_packets_v1_packet_type_ck;

alter table public.agentic_harness_packets_v1
    add constraint agentic_harness_packets_v1_packet_type_ck
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
        'UserQueryActionPacketV1',
        'RegistryDecisionPacketV1',
        'RegistryPatchAppliedPacketV1'
    ));

alter table public.agentic_harness_packets_v1
    drop constraint if exists agentic_harness_packets_v1_status_ck;

alter table public.agentic_harness_packets_v1
    add constraint agentic_harness_packets_v1_status_ck
    check (status in (
        'proposed',
        'enqueued',
        'running',
        'done',
        'blocked',
        'escalated',
        'expired',
        'applied',
        'rejected',
        'deferred'
    ));

alter table public.agentic_harness_queue_jobs_v1
    drop constraint if exists agentic_harness_queue_jobs_v1_queue_class_ck;

alter table public.agentic_harness_queue_jobs_v1
    add constraint agentic_harness_queue_jobs_v1_queue_class_ck
    check (queue_class in (
        'ingest_queue',
        'quality_queue',
        'research_queue',
        'governance_queue',
        'surface_action_queue',
        'replay_recompute_queue',
        'registry_apply_queue'
    ));

comment on table public.agentic_harness_queue_jobs_v1 is
    'Agentic Operating Harness v1: seven queue classes (ingest/quality/research/governance/surface_action/replay_recompute/registry_apply). registry_apply_queue (Patch 2) is consumed by registry_patch_executor to perform operator-approved horizon_provenance writes on the brain bundle.';

commit;
