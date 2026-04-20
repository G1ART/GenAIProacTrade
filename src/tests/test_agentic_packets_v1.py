"""Unit tests for the Agentic Operating Harness v1 packet contracts (AGH-1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_harness.contracts.packets_v1 import (
    AgenticPacketBaseV1,
    CoverageGapPacketV1,
    EvaluationPacketV1,
    EventTriggerPacketV1,
    IngestAlertPacketV1,
    LibraryIntegrityPacketV1,
    OverlayProposalPacketV1,
    PacketStatus,
    PACKET_STATUS_VALUES,
    PACKET_TYPE_TO_CLASS,
    PACKET_TYPES,
    PromotionGatePacketV1,
    RegistryUpdateProposalV1,
    ReplayLearningPacketV1,
    ResearchCandidatePacketV1,
    SourceArtifactPacketV1,
    TARGET_LAYERS,
    UserQueryActionPacketV1,
    deterministic_packet_id,
    validate_packet,
)
from agentic_harness.contracts.queues_v1 import (
    JOB_STATUS_VALUES,
    QUEUE_CLASSES,
    QueueJobV1,
    deterministic_job_id,
)


def _base_kwargs(**over) -> dict:
    base = {
        "packet_id": deterministic_packet_id(
            packet_type="IngestAlertPacketV1",
            created_by_agent="source_scout_agent",
            target_scope={"asset_id": "TRGP"},
        ),
        "packet_type": "IngestAlertPacketV1",
        "target_layer": "layer1_ingest",
        "created_by_agent": "source_scout_agent",
        "target_scope": {"asset_id": "TRGP"},
        "provenance_refs": ["registry://today/TRGP"],
        "confidence": 0.7,
        "blocking_reasons": [],
        "expiry_or_recheck_rule": "recheck at 2026-04-20T00:00:00Z",
        "payload": {
            "source_family": "earnings_transcript",
            "trigger_kind": "earnings_transcript_stale",
            "asset_ids": ["TRGP"],
        },
    }
    base.update(over)
    return base


def test_packet_types_vocabulary_is_stable():
    assert "IngestAlertPacketV1" in PACKET_TYPES
    assert "UserQueryActionPacketV1" in PACKET_TYPES
    # AGH v1 Patch 3: SpectrumRefreshRecordV1 joins the global vocab.
    assert "SpectrumRefreshRecordV1" in PACKET_TYPES
    assert "SpectrumRefreshRecordV1" in PACKET_TYPE_TO_CLASS
    assert len(set(PACKET_TYPES)) == len(PACKET_TYPES)


def test_status_vocabulary_covers_proposed_through_expired():
    for v in ("proposed", "enqueued", "running", "done", "blocked", "escalated", "expired"):
        assert v in PACKET_STATUS_VALUES


def test_target_layers_has_all_five():
    assert set(TARGET_LAYERS) == {
        "layer1_ingest",
        "layer2_library",
        "layer3_research",
        "layer4_governance",
        "layer5_surface",
    }


def test_ingest_alert_packet_happy_path_validates():
    pkt = IngestAlertPacketV1.model_validate(_base_kwargs())
    assert pkt.packet_type == "IngestAlertPacketV1"
    assert pkt.status == "proposed"
    assert pkt.created_at_utc, "created_at stamped automatically"


def test_base_rejects_empty_provenance_refs():
    with pytest.raises(ValidationError):
        IngestAlertPacketV1.model_validate(_base_kwargs(provenance_refs=[]))


def test_base_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        IngestAlertPacketV1.model_validate(_base_kwargs(confidence=1.5))


def test_forbidden_copy_tokens_rejected_in_payload():
    kw = _base_kwargs()
    kw["payload"]["hint_copy"] = "operators will definitely buy this"
    with pytest.raises(ValidationError):
        IngestAlertPacketV1.model_validate(kw)


def test_forbidden_copy_tokens_rejected_in_blocking_reasons():
    kw = _base_kwargs(blocking_reasons=["confirmed buy recommendation"])
    with pytest.raises(ValidationError):
        IngestAlertPacketV1.model_validate(kw)


def test_forbidden_copy_tokens_accepts_neutral_language():
    kw = _base_kwargs()
    kw["payload"]["summary"] = "management reiterated guidance tone."
    IngestAlertPacketV1.model_validate(kw)  # should not raise


def test_ingest_alert_requires_trigger_kind_vocab():
    kw = _base_kwargs()
    kw["payload"]["trigger_kind"] = "unknown_kind"
    with pytest.raises(ValidationError):
        IngestAlertPacketV1.model_validate(kw)


def test_event_trigger_packet_schema():
    kw = _base_kwargs(
        packet_type="EventTriggerPacketV1",
        payload={
            "trigger_kind": "earnings_transcript_stale",
            "asset_id": "TRGP",
            "expected_freshness_hours": 72,
        },
    )
    pkt = EventTriggerPacketV1.model_validate(kw)
    assert pkt.payload["asset_id"] == "TRGP"


def test_source_artifact_packet_requires_fetch_outcome_vocab():
    kw = _base_kwargs(
        packet_type="SourceArtifactPacketV1",
        payload={
            "source_family": "earnings_transcript",
            "artifact_kind": "transcript_text",
            "fetch_outcome": "ok",
        },
    )
    SourceArtifactPacketV1.model_validate(kw)
    kw["payload"]["fetch_outcome"] = "nonsense"
    with pytest.raises(ValidationError):
        SourceArtifactPacketV1.model_validate(kw)


def test_library_integrity_packet_severity_and_check_name_vocab():
    kw = _base_kwargs(
        packet_type="LibraryIntegrityPacketV1",
        target_layer="layer2_library",
        payload={
            "check_name": "pit_violation",
            "severity": "medium",
            "offending_refs": ["panel:TRGP:2025Q4"],
            "summary": "PIT asof precedes report_date",
        },
    )
    LibraryIntegrityPacketV1.model_validate(kw)
    kw["payload"]["severity"] = "critical"
    with pytest.raises(ValidationError):
        LibraryIntegrityPacketV1.model_validate(kw)


def test_coverage_gap_packet_requires_missing_asset_ids_list():
    kw = _base_kwargs(
        packet_type="CoverageGapPacketV1",
        target_layer="layer2_library",
        payload={
            "cohort_name": "combined_largecap_research_v1",
            "missing_asset_ids": ["TRGP"],
            "dimension": "transcripts_last_90d",
        },
    )
    CoverageGapPacketV1.model_validate(kw)
    kw["payload"]["missing_asset_ids"] = "TRGP"
    with pytest.raises(ValidationError):
        CoverageGapPacketV1.model_validate(kw)


def _persona_candidate_dict() -> dict:
    return {
        "candidate_id": "pcand_demo_v1",
        "persona": "quant_residual_analyst",
        "thesis_family": "residual_tightening_shortlist",
        "targeted_horizon": "short",
        "targeted_universe": "combined_largecap_research_v1",
        "evidence_refs": [{"kind": "seed", "pointer": "seed://x", "summary": "ok"}],
        "confidence": 0.62,
        "signal_type": "residual_tightening",
        "intended_overlay_type": "confidence_adjustment",
        "blocking_reasons": ["requires_pit_rule_certification"],
    }


def test_research_candidate_packet_embeds_persona_and_checks_signal_vocab():
    kw = _base_kwargs(
        packet_type="ResearchCandidatePacketV1",
        target_layer="layer3_research",
        payload={
            "persona_candidate_packet": _persona_candidate_dict(),
            "signal_type": "residual_tightening",
            "intended_overlay_type": "confidence_adjustment",
        },
    )
    pkt = ResearchCandidatePacketV1.model_validate(kw)
    assert pkt.payload["persona_candidate_packet"]["persona"] == "quant_residual_analyst"
    kw["payload"]["signal_type"] = "unknown_signal"
    with pytest.raises(ValidationError):
        ResearchCandidatePacketV1.model_validate(kw)


def test_overlay_proposal_packet_vocab():
    kw = _base_kwargs(
        packet_type="OverlayProposalPacketV1",
        target_layer="layer3_research",
        payload={
            "overlay_type": "regime_shift",
            "expected_direction_hint": "regime_changes",
            "why_it_matters": "management tone shifted toward caution",
        },
    )
    OverlayProposalPacketV1.model_validate(kw)
    kw["payload"]["overlay_type"] = "new_unknown_overlay"
    with pytest.raises(ValidationError):
        OverlayProposalPacketV1.model_validate(kw)


def test_evaluation_packet_requires_metrics_dict():
    kw = _base_kwargs(
        packet_type="EvaluationPacketV1",
        target_layer="layer4_governance",
        payload={
            "evaluation_kind": "regression_detected",
            "target_ref": "horizon:short",
            "metrics": {"ic_delta": -0.03},
        },
    )
    EvaluationPacketV1.model_validate(kw)
    kw["payload"]["metrics"] = ["ic_delta=-0.03"]
    with pytest.raises(ValidationError):
        EvaluationPacketV1.model_validate(kw)


def test_promotion_gate_packet_outcome_vocab():
    kw = _base_kwargs(
        packet_type="PromotionGatePacketV1",
        target_layer="layer4_governance",
        payload={
            "candidate_ref": "ResearchCandidatePacketV1:pkt_xyz",
            "gate_steps": [
                {"step": "pit", "outcome": "pass"},
                {"step": "monotonicity", "outcome": "deferred"},
            ],
            "overall_outcome": "deferred",
        },
    )
    PromotionGatePacketV1.model_validate(kw)
    kw["payload"]["overall_outcome"] = "maybe"
    with pytest.raises(ValidationError):
        PromotionGatePacketV1.model_validate(kw)


def test_registry_update_proposal_horizon_state_vocab_and_no_raw_mutation():
    kw = _base_kwargs(
        packet_type="RegistryUpdateProposalV1",
        target_layer="layer4_governance",
        payload={
            "target": "horizon_provenance",
            "from_state": "template_fallback",
            "to_state": "real_derived",
            "evidence_refs": ["validation://horizon:short:v1"],
        },
    )
    RegistryUpdateProposalV1.model_validate(kw)
    kw["payload"]["to_state"] = "some_other_state"
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)

    kw = _base_kwargs(
        packet_type="RegistryUpdateProposalV1",
        target_layer="layer4_governance",
        payload={
            "target": "horizon_provenance",
            "from_state": "template_fallback",
            "to_state": "real_derived",
            "evidence_refs": ["validation://horizon:short:v1"],
            "active_registry_mutation": {"registry_entry_id": "reg_short_demo_v0"},
        },
    )
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_replay_learning_packet_aging_vocab():
    kw = _base_kwargs(
        packet_type="ReplayLearningPacketV1",
        target_layer="layer4_governance",
        payload={
            "asset_id": "TRGP",
            "decision_event_id": "dec_v1",
            "overlay_aging_lineage": [
                {
                    "overlay_id": "ovr_short_transcript_guidance_tone_v1",
                    "aging_label": "aged_in_line",
                }
            ],
        },
    )
    ReplayLearningPacketV1.model_validate(kw)
    kw["payload"]["overlay_aging_lineage"][0]["aging_label"] = "degraded"
    with pytest.raises(ValidationError):
        ReplayLearningPacketV1.model_validate(kw)


def test_user_query_action_packet_requires_state_bundle_refs():
    kw = _base_kwargs(
        packet_type="UserQueryActionPacketV1",
        target_layer="layer5_surface",
        payload={
            "question": "왜 오늘 이 종목이 위로 올라왔지?",
            "routed_kind": "why_changed",
            "state_bundle_refs": ["packet:pkt_abc"],
            "llm_response": {
                "answer_ko": "오늘 Today 레지스트리 변동 요약 ...",
                "answer_en": "Today's registry delta summary ...",
                "cited_packet_ids": ["pkt_abc"],
                "fact_vs_interpretation_map": {"pkt_abc": "fact"},
                "recheck_rule": "recheck_next_tick",
                "blocking_reasons": [],
            },
            "guardrail_passed": True,
        },
    )
    UserQueryActionPacketV1.model_validate(kw)
    kw["payload"]["state_bundle_refs"] = []
    with pytest.raises(ValidationError):
        UserQueryActionPacketV1.model_validate(kw)


def test_validate_packet_type_dispatch():
    kw = _base_kwargs()
    pkt = validate_packet(dict(kw))
    assert isinstance(pkt, IngestAlertPacketV1)


def test_packet_type_class_table_covers_all_types():
    assert set(PACKET_TYPE_TO_CLASS.keys()) >= set(PACKET_TYPES)


# -----------------------------------------------------------------------------
# Queue shape tests
# -----------------------------------------------------------------------------


def test_queue_job_happy_path_stamps_times_and_accepts_status():
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id="pkt_xyz"),
            "queue_class": "ingest_queue",
            "packet_id": "pkt_xyz",
        }
    )
    assert job.status == "enqueued"
    assert job.enqueued_at_utc
    assert job.not_before_utc


def test_queue_job_rejects_unknown_queue_class():
    with pytest.raises(ValidationError):
        QueueJobV1.model_validate(
            {"job_id": "job_x", "queue_class": "bogus_queue", "packet_id": "pkt"}
        )


def test_queue_job_status_vocab_stable():
    assert set(JOB_STATUS_VALUES) == {"enqueued", "running", "done", "dlq", "expired"}
    # AGH v1 Patch 2 adds ``registry_apply_queue`` for operator-approved
    # RegistryUpdateProposalV1 jobs consumed by registry_patch_executor.
    # AGH v1 Patch 5 adds ``sandbox_queue`` for bounded ``validation_rerun``
    # jobs consumed by ``layer3_sandbox_executor_v1``.
    assert set(QUEUE_CLASSES) == {
        "ingest_queue",
        "quality_queue",
        "research_queue",
        "governance_queue",
        "surface_action_queue",
        "replay_recompute_queue",
        "registry_apply_queue",
        "sandbox_queue",
    }
