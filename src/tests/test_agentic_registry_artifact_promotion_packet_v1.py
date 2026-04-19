"""AGH v1 Patch 3 — artifact-promotion packet contract tests.

Covers REGISTRY_PROPOSAL_TARGETS vocabulary, RegistryUpdateProposalV1
validation for the new ``registry_entry_artifact_promotion`` target,
RegistryPatchAppliedPacketV1 snapshot shape, and the SpectrumRefreshRecordV1
schema.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_harness.contracts.packets_v1 import (
    PACKET_TYPE_TO_CLASS,
    PACKET_TYPES,
    REGISTRY_BUNDLE_HORIZONS,
    REGISTRY_PROPOSAL_TARGETS,
    SPECTRUM_REFRESH_MODES,
    SPECTRUM_REFRESH_OUTCOMES,
    RegistryPatchAppliedPacketV1,
    RegistryUpdateProposalV1,
    SpectrumRefreshRecordV1,
    deterministic_packet_id,
)


def test_registry_proposal_targets_vocab_stable():
    assert set(REGISTRY_PROPOSAL_TARGETS) == {
        "horizon_provenance",
        "registry_entry_artifact_promotion",
    }


def test_spectrum_refresh_vocab_stable():
    assert set(SPECTRUM_REFRESH_OUTCOMES) == {
        "recomputed",
        "carry_over_fixture_fallback",
        "carry_over_db_unavailable",
    }
    assert set(SPECTRUM_REFRESH_MODES) == {
        "full_recompute_from_validation",
        "fixture_fallback",
    }


def test_patch3_packet_type_in_global_vocab():
    assert "SpectrumRefreshRecordV1" in PACKET_TYPES
    assert PACKET_TYPE_TO_CLASS["SpectrumRefreshRecordV1"] is SpectrumRefreshRecordV1


def _proposal_kwargs(**over) -> dict:
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
        },
    )
    base = {
        "packet_id": pid,
        "packet_type": "RegistryUpdateProposalV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "promotion_arbiter_agent",
        "target_scope": {
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
        },
        "provenance_refs": ["packet:pkt_gate_demo"],
        "confidence": 0.9,
        "status": "escalated",
        "payload": {
            "target": "registry_entry_artifact_promotion",
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
            "from_active_artifact_id": "art_active_v0",
            "to_active_artifact_id": "art_challenger_v0",
            "from_challenger_artifact_ids": ["art_challenger_v0"],
            "to_challenger_artifact_ids": ["art_active_v0"],
            "evidence_refs": ["packet:pkt_gate_demo"],
        },
    }
    base.update(over)
    return base


def test_artifact_promotion_proposal_happy_path():
    pkt = RegistryUpdateProposalV1.model_validate(_proposal_kwargs())
    assert pkt.payload["target"] == "registry_entry_artifact_promotion"
    assert pkt.payload["from_active_artifact_id"] != pkt.payload["to_active_artifact_id"]


def test_artifact_promotion_rejects_unknown_target():
    kw = _proposal_kwargs()
    kw["payload"]["target"] = "some_new_target"
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_identical_from_to_active():
    kw = _proposal_kwargs()
    kw["payload"]["to_active_artifact_id"] = kw["payload"]["from_active_artifact_id"]
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_duplicate_challengers():
    kw = _proposal_kwargs()
    kw["payload"]["to_challenger_artifact_ids"] = ["art_x", "art_x"]
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_empty_challenger_string():
    kw = _proposal_kwargs()
    kw["payload"]["from_challenger_artifact_ids"] = [""]
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_unknown_horizon():
    kw = _proposal_kwargs()
    kw["payload"]["horizon"] = "super_short"
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_empty_evidence_refs():
    kw = _proposal_kwargs()
    kw["payload"]["evidence_refs"] = []
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def test_artifact_promotion_rejects_raw_active_registry_mutation():
    kw = _proposal_kwargs()
    kw["payload"]["active_registry_mutation"] = {"registry_entry_id": "x"}
    with pytest.raises(ValidationError):
        RegistryUpdateProposalV1.model_validate(kw)


def _applied_kwargs_artifact_promotion(**over) -> dict:
    pid = deterministic_packet_id(
        packet_type="RegistryPatchAppliedPacketV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "proposal_packet_id": "pkt_proposal",
            "horizon": "short",
            "target": "registry_entry_artifact_promotion",
            "outcome": "applied",
        },
    )
    base = {
        "packet_id": pid,
        "packet_type": "RegistryPatchAppliedPacketV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "registry_patch_executor",
        "target_scope": {
            "proposal_packet_id": "pkt_proposal",
            "horizon": "short",
            "target": "registry_entry_artifact_promotion",
        },
        "provenance_refs": ["packet:pkt_proposal", "packet:pkt_decision"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "outcome": "applied",
            "target": "registry_entry_artifact_promotion",
            "horizon": "short",
            "registry_entry_id": "reg_short_demo_v0",
            "cited_proposal_packet_id": "pkt_proposal",
            "cited_decision_packet_id": "pkt_decision",
            "applied_at_utc": "2026-04-19T10:00:00+00:00",
            "bundle_path": "/tmp/bundle.json",
            "before_snapshot": {
                "registry_entry": {
                    "registry_entry_id": "reg_short_demo_v0",
                    "horizon": "short",
                    "active_artifact_id": "art_active_v0",
                    "challenger_artifact_ids": ["art_challenger_v0"],
                }
            },
            "after_snapshot": {
                "registry_entry": {
                    "registry_entry_id": "reg_short_demo_v0",
                    "horizon": "short",
                    "active_artifact_id": "art_challenger_v0",
                    "challenger_artifact_ids": ["art_active_v0"],
                }
            },
        },
    }
    base.update(over)
    return base


def test_applied_packet_artifact_promotion_happy_path():
    pkt = RegistryPatchAppliedPacketV1.model_validate(
        _applied_kwargs_artifact_promotion()
    )
    assert pkt.payload["target"] == "registry_entry_artifact_promotion"
    assert pkt.payload["after_snapshot"]["registry_entry"]["active_artifact_id"] == (
        "art_challenger_v0"
    )


def test_applied_packet_artifact_promotion_conflict_skip_allows_empty_after():
    kw = _applied_kwargs_artifact_promotion()
    kw["payload"]["outcome"] = "conflict_skip"
    kw["payload"]["after_snapshot"] = {}
    pkt = RegistryPatchAppliedPacketV1.model_validate(kw)
    assert pkt.payload["outcome"] == "conflict_skip"


def test_applied_packet_artifact_promotion_requires_registry_entry_id():
    kw = _applied_kwargs_artifact_promotion()
    kw["payload"]["registry_entry_id"] = ""
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)


def test_applied_packet_rejects_invalid_horizon_for_artifact_promotion():
    kw = _applied_kwargs_artifact_promotion()
    kw["payload"]["horizon"] = "not_a_horizon"
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)


def _spectrum_refresh_kwargs(**over) -> dict:
    pid = deterministic_packet_id(
        packet_type="SpectrumRefreshRecordV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "applied_packet_id": "pkt_applied",
            "horizon": "short",
            "registry_entry_id": "reg_short_demo_v0",
        },
    )
    base = {
        "packet_id": pid,
        "packet_type": "SpectrumRefreshRecordV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "registry_patch_executor",
        "target_scope": {
            "applied_packet_id": "pkt_applied",
            "horizon": "short",
            "registry_entry_id": "reg_short_demo_v0",
        },
        "provenance_refs": [
            "packet:pkt_applied",
            "packet:pkt_proposal",
            "packet:pkt_decision",
        ],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "outcome": "recomputed",
            "refresh_mode": "full_recompute_from_validation",
            "needs_db_rebuild": False,
            "cited_applied_packet_id": "pkt_applied",
            "cited_proposal_packet_id": "pkt_proposal",
            "cited_decision_packet_id": "pkt_decision",
            "horizon": "short",
            "registry_entry_id": "reg_short_demo_v0",
            "before_row_count": 5,
            "after_row_count": 5,
            "before_row_asset_ids_sample": ["AAA", "BBB", "CCC"],
            "after_row_asset_ids_sample": ["AAA", "BBB", "CCC"],
            "refreshed_at_utc": "2026-04-19T10:05:00+00:00",
            "bundle_path": "/tmp/bundle.json",
            "blocking_reasons": [],
        },
    }
    base.update(over)
    return base


def test_spectrum_refresh_record_happy_path():
    pkt = SpectrumRefreshRecordV1.model_validate(_spectrum_refresh_kwargs())
    assert pkt.payload["outcome"] == "recomputed"
    assert pkt.payload["needs_db_rebuild"] is False


def test_spectrum_refresh_record_carry_over_fixture_fallback():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["outcome"] = "carry_over_fixture_fallback"
    kw["payload"]["refresh_mode"] = "fixture_fallback"
    kw["payload"]["needs_db_rebuild"] = True
    kw["payload"]["blocking_reasons"] = ["supabase_client_missing_or_fixture_mode"]
    pkt = SpectrumRefreshRecordV1.model_validate(kw)
    assert pkt.payload["needs_db_rebuild"] is True


def test_spectrum_refresh_record_rejects_unknown_outcome():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["outcome"] = "partial_rebuild"
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)


def test_spectrum_refresh_record_rejects_empty_cited_applied_packet_id():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["cited_applied_packet_id"] = ""
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)


def test_spectrum_refresh_record_rejects_negative_row_count():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["before_row_count"] = -1
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)


def test_spectrum_refresh_record_caps_sample_at_10():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["before_row_asset_ids_sample"] = [f"S{i}" for i in range(11)]
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)


def test_spectrum_refresh_record_rejects_active_registry_mutation():
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["active_registry_mutation"] = {"asset_id": "AAA"}
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)


def test_spectrum_refresh_record_horizon_vocab_enforced():
    assert set(REGISTRY_BUNDLE_HORIZONS) == {"short", "medium", "medium_long", "long"}
    kw = _spectrum_refresh_kwargs()
    kw["payload"]["horizon"] = "super_short"
    with pytest.raises(ValidationError):
        SpectrumRefreshRecordV1.model_validate(kw)
