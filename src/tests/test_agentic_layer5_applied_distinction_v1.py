"""AGH v1 Patch 2 - Layer 5 pending vs applied distinction tests.

The state reader must:
    * collect RegistryDecisionPacketV1 / RegistryPatchAppliedPacketV1 in the
      ``why_changed`` kind,
    * hide RegistryUpdateProposalV1 rows whose status has rolled forward to
      ``applied`` / ``rejected`` so the LLM does not surface them as pending.

The system prompt must reflect the ``applied`` vocabulary.
"""

from __future__ import annotations

from agentic_harness.agents.layer5_orchestrator import _SYSTEM_PROMPT, state_reader_agent
from agentic_harness.contracts.packets_v1 import (
    RegistryDecisionPacketV1,
    RegistryPatchAppliedPacketV1,
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


def _seed_full_chain(store: FixtureHarnessStore, *, proposal_status: str) -> dict[str, str]:
    horizon = "short"
    proposal_id = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={"horizon": horizon, "from_state": "template_fallback", "to_state": "real_derived"},
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": proposal_id,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {"horizon": horizon, "from_state": "template_fallback", "to_state": "real_derived"},
            "provenance_refs": [f"governance://{horizon}", "packet:pkt_gate"],
            "confidence": 0.8,
            "status": proposal_status,
            "payload": {
                "target": "horizon_provenance",
                "horizon": horizon,
                "from_state": "template_fallback",
                "to_state": "real_derived",
                "evidence_refs": [f"validation://horizon:{horizon}:v1"],
            },
        }
    )
    store.upsert_packet(proposal.model_dump())

    decision_id = deterministic_packet_id(
        packet_type="RegistryDecisionPacketV1",
        created_by_agent="operator:hyunmin",
        target_scope={"proposal_packet_id": proposal_id, "action": "approve"},
    )
    decision = RegistryDecisionPacketV1.model_validate(
        {
            "packet_id": decision_id,
            "packet_type": "RegistryDecisionPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "operator:hyunmin",
            "target_scope": {"proposal_packet_id": proposal_id, "action": "approve"},
            "provenance_refs": [f"packet:{proposal_id}"],
            "confidence": 1.0,
            "status": "done",
            "payload": {
                "action": "approve",
                "actor": "hyunmin",
                "reason": "operator-approved",
                "decision_at_utc": now_utc_iso(),
                "cited_proposal_packet_id": proposal_id,
            },
        }
    )
    store.upsert_packet(decision.model_dump())

    applied_id = deterministic_packet_id(
        packet_type="RegistryPatchAppliedPacketV1",
        created_by_agent="registry_patch_executor",
        target_scope={"proposal_packet_id": proposal_id, "outcome": "applied"},
    )
    applied = RegistryPatchAppliedPacketV1.model_validate(
        {
            "packet_id": applied_id,
            "packet_type": "RegistryPatchAppliedPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "registry_patch_executor",
            "target_scope": {"proposal_packet_id": proposal_id, "horizon": horizon, "target": "horizon_provenance"},
            "provenance_refs": [f"packet:{proposal_id}", f"packet:{decision_id}"],
            "confidence": 1.0,
            "status": "done",
            "payload": {
                "outcome": "applied",
                "target": "horizon_provenance",
                "horizon": horizon,
                "from_state": "template_fallback",
                "to_state": "real_derived",
                "cited_proposal_packet_id": proposal_id,
                "cited_decision_packet_id": decision_id,
                "applied_at_utc": now_utc_iso(),
                "bundle_path": "/tmp/x.json",
                "before_snapshot": {"horizon_provenance": {horizon: {"source": "template_fallback"}}},
                "after_snapshot": {"horizon_provenance": {horizon: {"source": "real_derived"}}},
            },
        }
    )
    store.upsert_packet(applied.model_dump())
    return {
        "proposal_id": proposal_id,
        "decision_id": decision_id,
        "applied_id": applied_id,
    }


def test_why_changed_bundle_includes_decision_and_applied_packets():
    store = FixtureHarnessStore()
    ids = _seed_full_chain(store, proposal_status="applied")

    bundle = state_reader_agent(store=store, asset_id="", routed_kind="why_changed")
    ptypes = {p.get("packet_type") for p in bundle["relevant_packets"]}
    assert "RegistryDecisionPacketV1" in ptypes
    assert "RegistryPatchAppliedPacketV1" in ptypes


def test_why_changed_hides_applied_proposals_from_pending_view():
    store = FixtureHarnessStore()
    ids = _seed_full_chain(store, proposal_status="applied")

    bundle = state_reader_agent(store=store, asset_id="", routed_kind="why_changed")
    # The applied proposal must NOT appear as a pending RegistryUpdateProposalV1
    # row in the state bundle.
    proposal_ids = {
        p.get("packet_id")
        for p in bundle["relevant_packets"]
        if p.get("packet_type") == "RegistryUpdateProposalV1"
    }
    assert ids["proposal_id"] not in proposal_ids
    # But the applied packet is surfaced so lineage is visible.
    applied_ids = {
        p.get("packet_id")
        for p in bundle["relevant_packets"]
        if p.get("packet_type") == "RegistryPatchAppliedPacketV1"
    }
    assert ids["applied_id"] in applied_ids


def test_why_changed_keeps_escalated_proposal_as_pending():
    store = FixtureHarnessStore()
    ids = _seed_full_chain(store, proposal_status="escalated")

    bundle = state_reader_agent(store=store, asset_id="", routed_kind="why_changed")
    proposal_ids = {
        p.get("packet_id")
        for p in bundle["relevant_packets"]
        if p.get("packet_type") == "RegistryUpdateProposalV1"
    }
    assert ids["proposal_id"] in proposal_ids


def test_system_prompt_explains_applied_vocabulary():
    assert "RegistryPatchAppliedPacketV1" in _SYSTEM_PROMPT
    assert "applied" in _SYSTEM_PROMPT
    assert "pending" in _SYSTEM_PROMPT
    # Guardrail still present.
    assert "NEVER claim" in _SYSTEM_PROMPT
