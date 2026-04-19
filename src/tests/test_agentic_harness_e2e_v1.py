"""End-to-end vertical slice for AGH v1 (AGH-9).

Drives a full Layer 1 → Layer 3 → Layer 4 → Layer 5 path against the
``FixtureHarnessStore`` so the test is entirely network-free.

Coverage:

    L1: Source Scout / Event Trigger / Ingest Coordinator create an
        IngestAlertPacketV1 and enqueue a job; the injected worker resolves
        it into a SourceArtifactPacketV1.
    L3: Persona Challenger / Skeptic / Meta-Governor create at least one
        ResearchCandidatePacketV1 and enqueue it.
    L4: Validation Referee / Promotion Arbiter / Fallback Honesty create a
        PromotionGatePacketV1 plus a RegistryUpdateProposalV1 (proposal-only,
        never mutating the real registry).
    L5: Action Router / State Reader / Founder/User Orchestrator surface the
        harness state via the FixtureProvider (no network), guardrails pass,
        and a UserQueryActionPacketV1 is written citing earlier packets.

Survey Q1–Q10 green is asserted as a smoke grid at the end.
"""

from __future__ import annotations

import pytest

from agentic_harness.agents.layer1_ingest import (
    event_trigger_agent,
    ingest_coordinator_agent,
    ingest_queue_worker,
    set_stale_asset_provider,
    set_transcript_fetcher,
    source_scout_agent,
)
from agentic_harness.agents.layer3_research import (
    _wrap_into_research_packet,
    meta_governor_agent,
    persona_challenger_agents,
    research_queue_worker,
    set_persona_candidate_factory,
    skeptic_falsification_analyst_agent,
)
from agentic_harness.agents.layer4_governance import (
    fallback_honesty_agent,
    promotion_arbiter_agent,
    set_gate_decision_provider,
    validation_referee_agent,
)
from agentic_harness.agents.layer5_orchestrator import (
    founder_user_orchestrator_agent,
)
from agentic_harness.contracts.packets_v1 import (
    IngestAlertPacketV1,
    PromotionGatePacketV1,
    RegistryUpdateProposalV1,
    ResearchCandidatePacketV1,
    SourceArtifactPacketV1,
    UserQueryActionPacketV1,
)
from agentic_harness.llm.provider import FixtureProvider
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


ASSET = "TRGP"


@pytest.fixture(autouse=True)
def _reset_providers():
    set_stale_asset_provider(None)
    set_transcript_fetcher(None)
    set_persona_candidate_factory(None)
    set_gate_decision_provider(None)
    yield
    set_stale_asset_provider(None)
    set_transcript_fetcher(None)
    set_persona_candidate_factory(None)
    set_gate_decision_provider(None)


def _run_l1(store: FixtureHarnessStore, now_iso: str) -> str:
    set_stale_asset_provider(
        lambda _s, _n: [
            {
                "asset_id": ASSET,
                "last_fetched_at_utc": "",
                "expected_freshness_hours": 72,
            }
        ]
    )
    stale = source_scout_agent(store, now_iso)
    assert len(stale) == 1
    trigger = event_trigger_agent(candidate=stale[0], now_iso=now_iso)
    res = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now_iso)
    assert res is not None
    alert_id = res["alert_packet_id"]
    saved_alert = store.get_packet(alert_id)
    assert saved_alert["packet_type"] == IngestAlertPacketV1.__name__
    # Claim + run the queued ingest job with a deterministic fetcher.
    set_transcript_fetcher(
        lambda meta: {
            "ok": True,
            "artifact_kind": "transcript_text",
            "artifact_ref": f"transcripts://{meta['asset_id']}/2025Q4",
            "fetched_at_utc": now_iso,
            "provenance_refs": [f"packet:{meta['alert_packet_id']}"],
            "confidence": 0.9,
        }
    )
    jobs = store.claim_next_jobs(
        queue_class="ingest_queue", now_utc=now_iso, max_jobs=1
    )
    assert jobs
    job = jobs[0]
    out = ingest_queue_worker(store, job)
    assert out["ok"] is True
    store.mark_job_result(job_id=job["job_id"], status="done", result_json=out)
    # Source artifact persisted.
    sa_id = out["source_artifact_packet_id"]
    sa = store.get_packet(sa_id)
    assert sa["packet_type"] == SourceArtifactPacketV1.__name__
    return alert_id


def _run_l3(store: FixtureHarnessStore, now_iso: str) -> str:
    set_persona_candidate_factory(
        lambda: [
            {
                "persona": "quant_residual_analyst",
                "thesis_family": "short_horizon_residual",
                "targeted_horizon": "short",
                "targeted_universe": "us_single_name_transcripts",
                "evidence_refs": [
                    {"pointer": f"registry://today/{ASSET}", "kind": "registry_row"}
                ],
                "confidence": 0.55,
                "overlay_recommendation": "lean_short_horizon_residual_tightening",
                "countercase": "If 3m realized vol regime snaps back to >2x ref, withdraw.",
                "gate_eligibility": {
                    "pit": True,
                    "coverage": True,
                },
                "provenance_summary": "seed v1 residual analyst playbook",
                "signal_type": "residual_tightening",
                "intended_overlay_type": "",
                "blocking_reasons": [],
            }
        ]
    )
    personas = persona_challenger_agents()
    assert len(personas) == 1
    personas = skeptic_falsification_analyst_agent(personas)
    research_packets = [_wrap_into_research_packet(pc) for pc in personas]
    out = meta_governor_agent(
        store=store, research_packets=research_packets, now_iso=now_iso
    )
    assert out["candidates_after_dedupe"] == 1
    assert out["enqueued_jobs"]
    jobs = store.claim_next_jobs(
        queue_class="research_queue", now_utc=now_iso, max_jobs=1
    )
    assert jobs
    job = jobs[0]
    worker_out = research_queue_worker(store, job)
    assert worker_out["ok"] is True
    store.mark_job_result(job_id=job["job_id"], status="done", result_json=worker_out)
    rc_id = worker_out["triaged_packet_id"]
    rc = store.get_packet(rc_id)
    assert rc["packet_type"] == ResearchCandidatePacketV1.__name__
    return rc_id


def _run_l4(store: FixtureHarnessStore, now_iso: str) -> tuple[str, str]:
    set_gate_decision_provider(
        lambda _s, _n: [
            {
                "horizon": "short",
                "from_state": "template_fallback",
                "proposed_state": "real_derived",
                "gate_booleans": {
                    "pit": True,
                    "monotonicity": False,  # one gate fails
                    "coverage": True,
                    "runtime_explainability": True,
                },
                "evidence_refs": ["validation://panel/accruals_short"],
                "candidate_ref": "registry://horizon/short",
            }
        ]
    )
    gate_inputs = validation_referee_agent(store, now_iso)
    assert len(gate_inputs) == 1
    gate_packets = promotion_arbiter_agent(gate_inputs=gate_inputs, now_iso=now_iso)
    assert gate_packets[0].payload["overall_outcome"] == "fail"
    store.upsert_packet(gate_packets[0].model_dump())
    fallback_proposal = fallback_honesty_agent(
        gate_input=gate_inputs[0], gate_packet=gate_packets[0], now_iso=now_iso
    )
    store.upsert_packet(fallback_proposal.model_dump())
    # Proposal-only doctrine: must be RegistryUpdateProposalV1, not a write.
    assert isinstance(fallback_proposal, RegistryUpdateProposalV1)
    assert isinstance(gate_packets[0], PromotionGatePacketV1)
    return gate_packets[0].packet_id, fallback_proposal.packet_id


def _run_l5(
    store: FixtureHarnessStore,
    *,
    alert_id: str,
    gate_id: str,
    proposal_id: str,
) -> str:
    out = founder_user_orchestrator_agent(
        store=store,
        question="왜 오늘 움직였지?",
        asset_id=ASSET,
        provider=FixtureProvider(),
    )
    assert out["routed_kind"] == "why_changed"
    assert out["guardrail_passed"] is True
    uq_id = out["user_query_action_packet_id"]
    pkt = store.get_packet(uq_id)
    assert pkt["packet_type"] == UserQueryActionPacketV1.__name__
    # Cites at least one packet from the harness state bundle.
    assert pkt["provenance_refs"], "user-query action packet must cite a bundle row"
    return uq_id


def test_agentic_harness_e2e_vertical_slice():
    store = FixtureHarnessStore()
    now = now_utc_iso()

    alert_id = _run_l1(store, now)
    _rc_id = _run_l3(store, now)
    gate_id, proposal_id = _run_l4(store, now)
    uq_id = _run_l5(
        store, alert_id=alert_id, gate_id=gate_id, proposal_id=proposal_id
    )

    # --- Survey Q1–Q10: smoke grid on the assembled harness state ------
    counts_by_layer = store.count_packets_by_layer()
    q_depths = store.queue_depth()

    # Q1  Layer 1 produced at least one ingest alert.
    assert counts_by_layer.get("layer1_ingest", 0) >= 1
    # Q2  Layer 3 produced at least one research candidate.
    assert counts_by_layer.get("layer3_research", 0) >= 1
    # Q3  Layer 4 produced at least one governance packet (gate or proposal).
    assert counts_by_layer.get("layer4_governance", 0) >= 1
    # Q4  Layer 5 produced exactly one user-query action packet.
    assert counts_by_layer.get("layer5_surface", 0) == 1
    # Q5  No directly-live registry writes were attempted (proposal doctrine):
    #     every layer-4 packet is a proposal or gate, nothing else.
    for r in store.list_packets(target_layer="layer4_governance", limit=100):
        assert r["packet_type"] in {
            "PromotionGatePacketV1",
            "RegistryUpdateProposalV1",
            "EvaluationPacketV1",
        }
    # Q6  Ingest/research/surface-action queues each moved through lifecycle
    #     without leaving zombie rows: each is either empty or flagged done.
    for qc in ("ingest_queue", "research_queue"):
        assert q_depths.get(qc, 0) == 0
    # Q7  Surface action queue holds exactly the one L5 action we emitted.
    assert q_depths.get("surface_action_queue", 0) == 1
    # Q8  The L5 packet carries provenance into the earlier packets, not a
    #     null bundle reference.
    uq_pkt = store.get_packet(uq_id)
    refs = list(uq_pkt.get("provenance_refs") or [])
    assert refs and not all(r.startswith("bundle:") for r in refs), (
        f"expected at least one concrete packet reference in provenance, got {refs}"
    )
    # Q9  No forbidden-copy tokens survived anywhere in the persisted packets
    #     (uses the same guardrail regex the packet validator enforces, not
    #     a naive substring check - "recommendation" / "buying-pattern" etc
    #     remain allowed; "recommend", "buy", "sell" as standalone words do not).
    from agentic_harness.llm.guardrails import guardrail_violations

    for pkt in store.list_packets(limit=200):
        hits = guardrail_violations([str(pkt)])
        assert not hits, f"forbidden tokens {hits} leaked into {pkt.get('packet_id')}"
    # Q10 Layer 4 honest-fallback proposal downgrades toward a real horizon
    #     state (not silent failure).
    proposal = store.get_packet(proposal_id)
    assert proposal["payload"]["to_state"] in {
        "real_derived_with_degraded_challenger",
        "template_fallback",
        "insufficient_evidence",
    }
