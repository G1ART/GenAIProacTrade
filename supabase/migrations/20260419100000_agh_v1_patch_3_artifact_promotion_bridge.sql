-- AGH v1 Patch 3: Artifact Promotion Bridge Closure (registry_entry active
-- <-> challenger swap + deterministic per-horizon spectrum refresh).
--
-- Extends the Patch 2 (20260418100000_agh_v1_patch_2_promotion_bridge.sql)
-- packet_type CHECK constraint so the agentic harness can persist the new
-- deterministic audit packet introduced in this patch:
--
--   * SpectrumRefreshRecordV1         (per-horizon refresh audit emitted by
--                                       registry_patch_executor after an
--                                       registry_entry_artifact_promotion
--                                       apply; outcome ∈
--                                         recomputed
--                                       | carry_over_fixture_fallback
--                                       | carry_over_db_unavailable)
--
-- Non-goals (deliberate): no new tables, no RLS changes, no column additions,
-- no status vocab or queue_class vocab changes. The artifact promotion apply
-- path reuses the Patch 2 registry_apply_queue and the Patch 2 applied/
-- rejected/deferred status terminal values. Canonical registry writes still
-- live in the brain bundle JSON (data/mvp/metis_brain_bundle_v0.json) and
-- are performed by the registry_patch_executor worker, not by raw SQL.

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
        'SpectrumRefreshRecordV1'
    ));

comment on table public.agentic_harness_packets_v1 is
    'Agentic Operating Harness v1: typed packet audit store. Patch 3 extends packet_type taxonomy to SpectrumRefreshRecordV1 (deterministic per-horizon refresh audit emitted alongside registry_entry_artifact_promotion applies).';

commit;
