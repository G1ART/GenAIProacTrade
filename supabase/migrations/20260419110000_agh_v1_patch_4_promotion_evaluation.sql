-- AGH v1 Patch 4: Validation -> Governance Bridge Closure.
--
-- Extends the Patch 3 (20260419100000_agh_v1_patch_3_artifact_promotion_bridge.sql)
-- packet_type CHECK constraint so the agentic harness can persist the new
-- deterministic upstream audit packet introduced in this patch:
--
--   * ValidationPromotionEvaluationV1  (per-evaluation record emitted by the
--                                       layer4_promotion_evaluator_v1 helper
--                                       whenever a completed factor_validation
--                                       run is inspected for artifact
--                                       promotion; outcome ∈
--                                         proposal_emitted
--                                       | blocked_by_gate
--                                       | blocked_same_as_active
--                                       | blocked_missing_evidence
--                                       | blocked_bundle_integrity)
--
-- Non-goals (deliberate): no new tables, no RLS changes, no column additions,
-- no status vocab or queue_class vocab changes. Proposals emitted by the
-- evaluator still ride the Patch 2 governance_queue -> registry_apply_queue
-- pipeline; the canonical registry write path (validate_merged_bundle_dict +
-- write_bundle_json_atomic) is unchanged.

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
        'ValidationPromotionEvaluationV1'
    ));

comment on table public.agentic_harness_packets_v1 is
    'Agentic Operating Harness v1: typed packet audit store. Patch 4 extends packet_type taxonomy to ValidationPromotionEvaluationV1 (upstream validation-driven promotion evaluation emitted by layer4_promotion_evaluator_v1 alongside any auto-generated RegistryUpdateProposalV1(target=registry_entry_artifact_promotion)).';

commit;
