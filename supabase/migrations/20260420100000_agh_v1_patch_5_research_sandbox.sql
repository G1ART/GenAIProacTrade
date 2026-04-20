-- AGH v1 Patch 5: Research Ask / bounded sandbox closure.
--
-- Extends the Patch 4 (20260419110000_agh_v1_patch_4_promotion_evaluation.sql)
-- packet_type CHECK constraint + the Patch 2
-- (20260418100000_agh_v1_patch_2_promotion_bridge.sql) queue_class CHECK
-- constraint so the agentic harness can persist the two new packets and one
-- new queue class introduced by Patch 5:
--
--   * SandboxRequestPacketV1  (operator / research_ask-originated bounded
--                              sandbox request; sandbox_kind limited to
--                              'validation_rerun' in Patch 5)
--   * SandboxResultPacketV1   (worker-emitted outcome paired with the
--                              request packet via cited_request_packet_id)
--   * sandbox_queue           (queue_class consumed by the Layer 3
--                              sandbox_executor_v1 worker)
--
-- Non-goals (deliberate): no new tables, no RLS changes, no status vocab
-- changes, no column additions. The active registry is NEVER mutated via
-- the sandbox path; operator-gated promotion still rides Patch 2/3/4 rails.

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
        'RegistryPatchAppliedPacketV1',
        'SpectrumRefreshRecordV1',
        'ValidationPromotionEvaluationV1',
        'SandboxRequestPacketV1',
        'SandboxResultPacketV1'
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
        'registry_apply_queue',
        'sandbox_queue'
    ));

comment on table public.agentic_harness_packets_v1 is
    'Agentic Operating Harness v1: typed packet audit store. Patch 5 extends packet_type taxonomy to SandboxRequestPacketV1 + SandboxResultPacketV1 (bounded research sandbox closed-loop; Patch 5 supports only sandbox_kind=validation_rerun).';

comment on table public.agentic_harness_queue_jobs_v1 is
    'Agentic Operating Harness v1: eight queue classes (ingest/quality/research/governance/surface_action/replay_recompute/registry_apply/sandbox). sandbox_queue (Patch 5) is consumed by layer3_sandbox_executor_v1 to record validation_rerun outcomes without touching the active registry.';

commit;
