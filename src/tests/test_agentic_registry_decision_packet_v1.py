"""AGH v1 Patch 2 - RegistryDecisionPacketV1 / RegistryPatchAppliedPacketV1 schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_harness.contracts.packets_v1 import (
    PACKET_STATUS_VALUES,
    PACKET_TYPE_TO_CLASS,
    PACKET_TYPES,
    REGISTRY_DECISION_ACTIONS,
    REGISTRY_PATCH_OUTCOMES,
    RegistryDecisionPacketV1,
    RegistryPatchAppliedPacketV1,
    deterministic_packet_id,
)


def _decision_kwargs(**over) -> dict:
    pid = deterministic_packet_id(
        packet_type="RegistryDecisionPacketV1",
        created_by_agent="operator:hyunmin",
        target_scope={"proposal_packet_id": "pkt_proposal", "action": "approve"},
    )
    base = {
        "packet_id": pid,
        "packet_type": "RegistryDecisionPacketV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "operator:hyunmin",
        "target_scope": {
            "proposal_packet_id": "pkt_proposal",
            "horizon": "short",
            "action": "approve",
        },
        "provenance_refs": ["packet:pkt_proposal", "packet:pkt_gate"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "action": "approve",
            "actor": "hyunmin",
            "reason": "promotion gate passed; operator-approved",
            "decision_at_utc": "2026-04-18T10:00:00+00:00",
            "cited_proposal_packet_id": "pkt_proposal",
            "cited_gate_packet_id": "pkt_gate",
        },
    }
    base.update(over)
    return base


def _applied_kwargs(**over) -> dict:
    pid = deterministic_packet_id(
        packet_type="RegistryPatchAppliedPacketV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "proposal_packet_id": "pkt_proposal",
            "horizon": "short",
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
            "target": "horizon_provenance",
        },
        "provenance_refs": ["packet:pkt_proposal", "packet:pkt_decision"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "outcome": "applied",
            "target": "horizon_provenance",
            "horizon": "short",
            "from_state": "template_fallback",
            "to_state": "real_derived",
            "cited_proposal_packet_id": "pkt_proposal",
            "cited_decision_packet_id": "pkt_decision",
            "applied_at_utc": "2026-04-18T10:05:00+00:00",
            "bundle_path": "/tmp/bundle.json",
            "before_snapshot": {
                "horizon_provenance": {"short": {"source": "template_fallback"}}
            },
            "after_snapshot": {
                "horizon_provenance": {"short": {"source": "real_derived"}}
            },
        },
    }
    base.update(over)
    return base


def test_patch2_packet_types_are_in_global_vocab():
    assert "RegistryDecisionPacketV1" in PACKET_TYPES
    assert "RegistryPatchAppliedPacketV1" in PACKET_TYPES
    assert PACKET_TYPE_TO_CLASS["RegistryDecisionPacketV1"] is RegistryDecisionPacketV1
    assert (
        PACKET_TYPE_TO_CLASS["RegistryPatchAppliedPacketV1"]
        is RegistryPatchAppliedPacketV1
    )


def test_patch2_packet_status_vocab_extended():
    for s in ("applied", "rejected", "deferred"):
        assert s in PACKET_STATUS_VALUES


def test_decision_vocab_stable():
    assert set(REGISTRY_DECISION_ACTIONS) == {"approve", "reject", "defer"}
    assert set(REGISTRY_PATCH_OUTCOMES) == {"applied", "conflict_skip"}


def test_decision_packet_happy_path_validates():
    pkt = RegistryDecisionPacketV1.model_validate(_decision_kwargs())
    assert pkt.payload["action"] == "approve"
    assert pkt.payload["cited_proposal_packet_id"] == "pkt_proposal"


def test_decision_packet_rejects_unknown_action():
    kw = _decision_kwargs()
    kw["payload"]["action"] = "maybe"
    with pytest.raises(ValidationError):
        RegistryDecisionPacketV1.model_validate(kw)


def test_decision_packet_rejects_empty_proposal_id():
    kw = _decision_kwargs()
    kw["payload"]["cited_proposal_packet_id"] = ""
    with pytest.raises(ValidationError):
        RegistryDecisionPacketV1.model_validate(kw)


def test_decision_packet_rejects_raw_active_registry_mutation():
    kw = _decision_kwargs()
    kw["payload"]["active_registry_mutation"] = {"artifact_id": "art_x"}
    with pytest.raises(ValidationError):
        RegistryDecisionPacketV1.model_validate(kw)


def test_decision_packet_rejects_forbidden_reason_copy():
    kw = _decision_kwargs()
    kw["payload"]["reason"] = "operator approves buy signal today"
    with pytest.raises(ValidationError):
        RegistryDecisionPacketV1.model_validate(kw)


def test_applied_packet_happy_path_validates():
    pkt = RegistryPatchAppliedPacketV1.model_validate(_applied_kwargs())
    assert pkt.payload["outcome"] == "applied"
    assert pkt.payload["before_snapshot"]["horizon_provenance"]["short"]["source"] == "template_fallback"


def test_applied_packet_rejects_unknown_outcome():
    kw = _applied_kwargs()
    kw["payload"]["outcome"] = "partial"
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)


def test_applied_packet_rejects_invalid_horizon_state():
    kw = _applied_kwargs()
    kw["payload"]["to_state"] = "some_other_state"
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)


def test_applied_packet_rejects_raw_active_registry_mutation():
    kw = _applied_kwargs()
    kw["payload"]["active_registry_mutation"] = {"artifact_id": "art_x"}
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)


def test_applied_packet_allows_empty_after_snapshot_for_conflict_skip():
    kw = _applied_kwargs()
    kw["payload"]["outcome"] = "conflict_skip"
    kw["payload"]["after_snapshot"] = {}
    pkt = RegistryPatchAppliedPacketV1.model_validate(kw)
    assert pkt.payload["outcome"] == "conflict_skip"
    assert pkt.payload["after_snapshot"] == {}


def test_applied_packet_requires_before_and_after_snapshot_keys():
    kw = _applied_kwargs()
    del kw["payload"]["before_snapshot"]
    with pytest.raises(ValidationError):
        RegistryPatchAppliedPacketV1.model_validate(kw)
