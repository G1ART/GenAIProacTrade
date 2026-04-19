"""Layer 4 (validation -> registry proposal) tests (AGH-7)."""

from __future__ import annotations

import pytest

from agentic_harness.agents import layer4_governance
from agentic_harness.agents.layer4_governance import (
    governance_queue_worker,
    promotion_arbiter_agent,
    propose_layer4_cadence,
    set_gate_decision_provider,
    set_regression_provider,
    validation_referee_agent,
)
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


@pytest.fixture(autouse=True)
def _reset_layer4():
    set_gate_decision_provider(None)
    set_regression_provider(None)
    yield
    set_gate_decision_provider(None)
    set_regression_provider(None)


def _passing_gate_input() -> dict:
    return {
        "horizon": "short",
        "from_state": "template_fallback",
        "proposed_state": "real_derived",
        "gate_booleans": {
            "pit": True,
            "monotonicity": True,
            "coverage": True,
            "runtime_explainability": True,
        },
        "evidence_refs": ["validation://horizon:short:accruals:v1"],
        "candidate_ref": "ResearchCandidatePacketV1:pkt_demo",
    }


def _failing_gate_input() -> dict:
    return {
        "horizon": "medium_long",
        "from_state": "template_fallback",
        "proposed_state": "real_derived",
        "gate_booleans": {
            "pit": True,
            "monotonicity": False,
            "coverage": True,
            "runtime_explainability": False,
        },
        "evidence_refs": ["validation://horizon:medium_long:accruals:v1"],
    }


def test_validation_referee_filters_same_state_transitions():
    set_gate_decision_provider(
        lambda s, t: [
            {"horizon": "short", "from_state": "template_fallback", "proposed_state": "template_fallback", "gate_booleans": {}},
            _passing_gate_input(),
        ]
    )
    out = validation_referee_agent(FixtureHarnessStore(), now_utc_iso())
    assert len(out) == 1


def test_promotion_arbiter_builds_gate_packets_with_outcome():
    packets = promotion_arbiter_agent(
        gate_inputs=[_passing_gate_input(), _failing_gate_input()],
        now_iso=now_utc_iso(),
    )
    assert len(packets) == 2
    assert packets[0].payload["overall_outcome"] == "pass"
    assert packets[1].payload["overall_outcome"] == "fail"


def test_gate_pass_produces_upgrade_proposal():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [_passing_gate_input()])
    summary = propose_layer4_cadence(store, now_utc_iso())
    assert summary["registry_update_proposals"] == 1
    assert summary["proposal_outcomes"][0] == {
        "from": "template_fallback",
        "to": "real_derived",
    }
    proposals = store.list_packets(packet_type="RegistryUpdateProposalV1")
    assert proposals[0]["payload"]["to_state"] == "real_derived"


def test_gate_fail_produces_honest_fallback_proposal_with_blocking_reasons():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [_failing_gate_input()])
    summary = propose_layer4_cadence(store, now_utc_iso())
    outcome = summary["proposal_outcomes"][0]
    # from=template_fallback proposed=real_derived, but gate fails -> honest fallback
    assert outcome["to"] == "real_derived_with_degraded_challenger"
    proposals = store.list_packets(packet_type="RegistryUpdateProposalV1")
    # The failing gates (monotonicity + runtime_explainability) land as blocking reasons.
    reasons = proposals[0]["blocking_reasons"]
    assert "gate_fail:monotonicity" in reasons
    assert "gate_fail:runtime_explainability" in reasons


def test_proposal_never_carries_raw_registry_mutation_payload():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [_passing_gate_input()])
    propose_layer4_cadence(store, now_utc_iso())
    for p in store.list_packets(packet_type="RegistryUpdateProposalV1"):
        assert "active_registry_mutation" not in (p.get("payload") or {})


def test_proposal_enqueues_governance_queue_job():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [_passing_gate_input()])
    propose_layer4_cadence(store, now_utc_iso())
    assert store.queue_depth()["governance_queue"] == 1


def test_regression_watcher_emits_evaluation_packet():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [])
    set_regression_provider(
        lambda s, t: [
            {
                "target_ref": "horizon:short",
                "metrics": {"ic_delta": -0.04},
                "provenance_refs": ["validation://horizon:short:accruals:v1"],
            }
        ]
    )
    summary = propose_layer4_cadence(store, now_utc_iso())
    assert summary["regression_events"] == 1


def test_governance_queue_worker_promotes_to_surface_action_queue():
    store = FixtureHarnessStore()
    set_gate_decision_provider(lambda s, t: [_passing_gate_input()])
    propose_layer4_cadence(store, now_utc_iso())
    claimed = store.claim_next_jobs(queue_class="governance_queue", now_utc=now_utc_iso())
    assert len(claimed) == 1
    res = governance_queue_worker(store, claimed[0])
    assert res["ok"]
    assert store.queue_depth()["surface_action_queue"] == 1
    assert store.get_packet(res["escalated_packet_id"])["status"] == "escalated"
