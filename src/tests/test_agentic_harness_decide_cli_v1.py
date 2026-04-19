"""AGH v1 Patch 2 - harness-decide CLI + record_registry_decision tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_harness import runtime
from agentic_harness.agents.layer4_governance import (
    DecisionError,
    record_registry_decision,
)
from agentic_harness.contracts.packets_v1 import (
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_proposal(store, *, status="proposed") -> str:
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={"horizon": "short", "from_state": "template_fallback", "to_state": "real_derived"},
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "horizon": "short",
                "from_state": "template_fallback",
                "to_state": "real_derived",
            },
            "provenance_refs": ["governance://short", "packet:pkt_gate_demo"],
            "confidence": 0.8,
            "status": status,
            "payload": {
                "target": "horizon_provenance",
                "from_state": "template_fallback",
                "to_state": "real_derived",
                "horizon": "short",
                "evidence_refs": ["validation://horizon:short:v1"],
            },
        }
    )
    store.upsert_packet(proposal.model_dump())
    return proposal.packet_id


@pytest.fixture(autouse=True)
def _reset_fixture_store():
    runtime._FIXTURE_STORE = None
    yield
    runtime._FIXTURE_STORE = None


def test_record_decision_approve_enqueues_apply_job_and_keeps_escalated():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    res = record_registry_decision(
        store,
        proposal_id=pid,
        action="approve",
        actor="hyunmin",
        reason="ops-approved for e2e",
        now_iso=now_utc_iso(),
    )
    assert res["ok"] is True
    assert res["action"] == "approve"
    assert res["apply_job_id"]
    assert res["proposal_status"] == "escalated"
    assert store.get_packet(pid)["status"] == "escalated"
    # Decision packet recorded.
    decisions = store.list_packets(packet_type="RegistryDecisionPacketV1")
    assert len(decisions) == 1
    assert decisions[0]["payload"]["action"] == "approve"
    # Apply job enqueued.
    assert store.queue_depth()["registry_apply_queue"] == 1


def test_record_decision_reject_marks_proposal_rejected_and_no_job():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    res = record_registry_decision(
        store,
        proposal_id=pid,
        action="reject",
        actor="hyunmin",
        reason="insufficient evidence",
        now_iso=now_utc_iso(),
    )
    assert res["proposal_status"] == "rejected"
    assert res["apply_job_id"] is None
    assert store.get_packet(pid)["status"] == "rejected"
    assert store.queue_depth().get("registry_apply_queue", 0) == 0


def test_record_decision_defer_sets_deferred_and_keeps_revisit_hint():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    res = record_registry_decision(
        store,
        proposal_id=pid,
        action="defer",
        actor="hyunmin",
        reason="wait for next data pull",
        now_iso=now_utc_iso(),
        next_revisit_hint_utc="2026-04-20T00:00:00+00:00",
    )
    assert res["proposal_status"] == "deferred"
    assert store.get_packet(pid)["status"] == "deferred"
    decisions = store.list_packets(packet_type="RegistryDecisionPacketV1")
    assert decisions[0]["payload"]["next_revisit_hint_utc"] == "2026-04-20T00:00:00+00:00"
    assert decisions[0]["expiry_or_recheck_rule"].startswith("next_revisit:")


def test_record_decision_rejects_duplicate_decision():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    record_registry_decision(
        store,
        proposal_id=pid,
        action="approve",
        actor="hyunmin",
        reason="first-approve",
        now_iso=now_utc_iso(),
    )
    with pytest.raises(DecisionError):
        record_registry_decision(
            store,
            proposal_id=pid,
            action="reject",
            actor="hyunmin",
            reason="second-decision-should-be-blocked",
            now_iso=now_utc_iso(),
        )


def test_record_decision_rejects_terminal_proposal_status():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    store.set_packet_status(pid, "applied")
    with pytest.raises(DecisionError):
        record_registry_decision(
            store,
            proposal_id=pid,
            action="reject",
            actor="hyunmin",
            reason="too-late",
            now_iso=now_utc_iso(),
        )


def test_record_decision_rejects_forbidden_copy_reason():
    store = FixtureHarnessStore()
    pid = _seed_proposal(store, status="escalated")
    # Forbidden copy tokens are scanned by the packet base validator, so the
    # model_validate inside record_registry_decision raises ValueError.
    with pytest.raises(ValueError):
        record_registry_decision(
            store,
            proposal_id=pid,
            action="approve",
            actor="hyunmin",
            reason="operator says buy this ticker today",
            now_iso=now_utc_iso(),
        )


def test_perform_decision_returns_decision_error_as_ok_false():
    res = runtime.perform_decision(
        proposal_id="pkt_does_not_exist",
        action="approve",
        actor="hyunmin",
        reason="",
        use_fixture=True,
    )
    assert res["ok"] is False
    assert "proposal packet not found" in res["error"]


def test_harness_decide_cli_approve_happy_path_writes_decision_and_enqueues_apply_job(tmp_path):
    # Share process-wide fixture store: use runtime.perform_decision directly
    # (the CLI subprocess would start with a fresh module state and thus
    # an empty fixture store).
    store = runtime._get_fixture_store()
    pid = _seed_proposal(store, status="escalated")

    res = runtime.perform_decision(
        proposal_id=pid,
        action="approve",
        actor="ops@example.com",
        reason="e2e-approved for tests",
        use_fixture=True,
    )
    assert res["ok"] is True
    assert res["apply_job_id"]
    assert store.queue_depth()["registry_apply_queue"] == 1


def test_harness_decide_cli_surfaces_process_invocation(tmp_path, monkeypatch):
    # End-to-end CLI smoke: verify the subcommand is wired and exits non-zero
    # when the proposal_id is missing.
    script = str(REPO_ROOT / "src" / "main.py")
    env = {
        **{k: v for k, v in __import__("os").environ.items()},
    }
    cp = subprocess.run(
        [
            sys.executable,
            script,
            "harness-decide",
            "--proposal-id",
            "pkt_does_not_exist",
            "--action",
            "approve",
            "--actor",
            "tester",
            "--reason",
            "cli smoke",
            "--use-fixture",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    # Returns non-zero because the proposal doesn't exist; stdout JSON must
    # still be structured ok=False.
    assert cp.returncode == 1
    out = json.loads(cp.stdout)
    assert out["ok"] is False
    assert "proposal packet not found" in json.dumps(out)
