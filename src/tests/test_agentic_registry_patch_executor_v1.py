"""AGH v1 Patch 2 - registry_patch_executor worker tests.

Covers the operator-approved write path against a tmp brain bundle:
    * approve happy path (escalated -> applied, bundle mutated)
    * from_state mismatch -> conflict_skip, bundle unchanged, proposal deferred
    * idempotent skip when proposal status is not ``escalated``
    * apply job with no approve decision -> DLQ (retryable=False)
    * bundle validation failure -> DLQ, bundle unchanged
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_harness.agents.layer4_registry_patch_executor import (
    registry_patch_executor,
)
from agentic_harness.contracts.packets_v1 import (
    RegistryDecisionPacketV1,
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


def _write_bundle(path: Path, *, horizon: str, source: str) -> str:
    bundle = {
        "schema_version": 1,
        "as_of_utc": "2026-04-18T00:00:00+00:00",
        "price_layer_note": "",
        "artifacts": [],
        "promotion_gates": [],
        "registry_entries": [],
        "spectrum_rows_by_horizon": {},
        "horizon_provenance": {horizon: {"source": source}},
    }
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.read_text(encoding="utf-8")


@pytest.fixture
def bundle_path(tmp_path, monkeypatch):
    p = tmp_path / "bundle.json"
    _write_bundle(p, horizon="short", source="template_fallback")
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))
    return p


def _seed_proposal(store, *, horizon="short", from_state="template_fallback", to_state="real_derived") -> str:
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={"horizon": horizon, "from_state": from_state, "to_state": to_state},
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "horizon": horizon,
                "from_state": from_state,
                "to_state": to_state,
            },
            "provenance_refs": [f"governance://{horizon}", "packet:pkt_gate_demo"],
            "confidence": 0.8,
            "status": "escalated",
            "payload": {
                "target": "horizon_provenance",
                "from_state": from_state,
                "to_state": to_state,
                "horizon": horizon,
                "evidence_refs": [f"validation://horizon:{horizon}:v1"],
            },
        }
    )
    store.upsert_packet(proposal.model_dump())
    return proposal.packet_id


def _seed_approve_decision(store, proposal_id: str) -> str:
    did = deterministic_packet_id(
        packet_type="RegistryDecisionPacketV1",
        created_by_agent="operator:test",
        target_scope={"proposal_packet_id": proposal_id, "action": "approve"},
    )
    decision = RegistryDecisionPacketV1.model_validate(
        {
            "packet_id": did,
            "packet_type": "RegistryDecisionPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "operator:test",
            "target_scope": {"proposal_packet_id": proposal_id, "action": "approve"},
            "provenance_refs": [f"packet:{proposal_id}"],
            "confidence": 1.0,
            "status": "done",
            "payload": {
                "action": "approve",
                "actor": "test",
                "reason": "operator-approved for test",
                "decision_at_utc": now_utc_iso(),
                "cited_proposal_packet_id": proposal_id,
            },
        }
    )
    store.upsert_packet(decision.model_dump())
    return decision.packet_id


def test_approve_happy_path_applies_and_marks_proposal_applied(bundle_path):
    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(store)
    decision_id = _seed_approve_decision(store, proposal_id)

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is True
    assert res["outcome"] == "applied"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["horizon_provenance"]["short"]["source"] == "real_derived"
    assert bundle["horizon_provenance"]["short"]["last_governed_proposal_packet_id"] == proposal_id
    assert bundle["horizon_provenance"]["short"]["last_governed_decision_packet_id"] == decision_id

    applied_pkt = store.get_packet(res["applied_packet_id"])
    assert applied_pkt["payload"]["outcome"] == "applied"
    assert applied_pkt["payload"]["before_snapshot"]["horizon_provenance"]["short"]["source"] == "template_fallback"
    assert applied_pkt["payload"]["after_snapshot"]["horizon_provenance"]["short"]["source"] == "real_derived"

    assert store.get_packet(proposal_id)["status"] == "applied"


def test_from_state_mismatch_produces_conflict_skip_and_defers_proposal(bundle_path):
    # Bundle is ``real_derived`` already, but proposal claims from=template_fallback.
    _write_bundle(bundle_path, horizon="short", source="real_derived")
    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(
        store, from_state="template_fallback", to_state="real_derived"
    )
    _seed_approve_decision(store, proposal_id)

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is True
    assert res["outcome"] == "conflict_skip"
    # Bundle unchanged.
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["horizon_provenance"]["short"]["source"] == "real_derived"
    assert "last_governed_proposal_packet_id" not in bundle["horizon_provenance"]["short"]

    applied_pkt = store.get_packet(res["applied_packet_id"])
    assert applied_pkt["payload"]["outcome"] == "conflict_skip"
    assert applied_pkt["payload"]["after_snapshot"] == {}

    assert store.get_packet(proposal_id)["status"] == "deferred"


def test_already_applied_proposal_is_skipped_idempotently(bundle_path):
    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(store)
    _seed_approve_decision(store, proposal_id)
    store.set_packet_status(proposal_id, "applied")

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is True
    assert res.get("skipped") is True
    # Bundle must remain on initial state.
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["horizon_provenance"]["short"]["source"] == "template_fallback"


def test_missing_approve_decision_sends_job_to_dlq(bundle_path):
    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(store)
    # No decision packet seeded.

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is False
    assert res["retryable"] is False
    assert "no_approve_decision" in res["error"]

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["horizon_provenance"]["short"]["source"] == "template_fallback"


def test_missing_horizon_in_bundle_produces_conflict_skip_without_crash(bundle_path):
    # Bundle lacks the requested horizon entry entirely.
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["horizon_provenance"] = {}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(store)
    _seed_approve_decision(store, proposal_id)

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is True
    assert res["outcome"] == "conflict_skip"
    # Proposal must not be applied.
    assert store.get_packet(proposal_id)["status"] == "deferred"


def test_missing_bundle_file_fails_without_mutation(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist.json"
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(missing))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))

    store = FixtureHarnessStore()
    proposal_id = _seed_proposal(store)
    _seed_approve_decision(store, proposal_id)

    res = registry_patch_executor(store, {"packet_id": proposal_id})

    assert res["ok"] is False
    assert res["retryable"] is False
    assert "bundle_missing" in res["error"]
    assert not missing.exists()
