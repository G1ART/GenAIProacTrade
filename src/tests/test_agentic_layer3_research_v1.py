"""Layer 3 (challenger cycle) tests (AGH-6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentic_harness.agents import layer3_research
from agentic_harness.agents.layer3_research import (
    meta_governor_agent,
    persona_challenger_agents,
    propose_layer3_cadence,
    research_queue_worker,
    set_persona_candidate_factory,
    skeptic_falsification_analyst_agent,
)
from agentic_harness.scheduler.cadences import should_run_cadence
from agentic_harness.scheduler.tick import LayerCadenceSpec, QueueSpec, run_one_tick
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


@pytest.fixture(autouse=True)
def _reset_layer3():
    set_persona_candidate_factory(None)
    yield
    set_persona_candidate_factory(None)


def _demo_candidates(with_counter_case: bool = True) -> list[dict]:
    return [
        {
            "persona": "quant_residual_analyst",
            "thesis_family": "accruals residual tightening on large-cap next_month",
            "targeted_horizon": "short",
            "targeted_universe": "combined_largecap_research_v1",
            "evidence_refs": [{"kind": "seed", "pointer": "seed://a", "summary": "ok"}],
            "confidence": 0.55,
            "countercase": "possible crowding" if with_counter_case else "",
            "signal_type": "residual_tightening",
            "intended_overlay_type": "confidence_adjustment",
            "blocking_reasons": ["requires_pit_rule_certification"],
        }
    ]


def test_persona_challenger_agents_build_pydantic_packets():
    set_persona_candidate_factory(lambda: _demo_candidates())
    packets = persona_challenger_agents()
    assert len(packets) == 1
    assert packets[0].persona == "quant_residual_analyst"


def test_skeptic_adds_no_counter_interpretation_when_missing():
    set_persona_candidate_factory(lambda: _demo_candidates(with_counter_case=False))
    packets = persona_challenger_agents()
    patched = skeptic_falsification_analyst_agent(packets)
    assert "no_counter_interpretation" in patched[0].blocking_reasons


def test_skeptic_preserves_existing_blocking_reasons_when_counter_present():
    set_persona_candidate_factory(lambda: _demo_candidates(with_counter_case=True))
    packets = persona_challenger_agents()
    patched = skeptic_falsification_analyst_agent(packets)
    assert "no_counter_interpretation" not in patched[0].blocking_reasons


def test_meta_governor_dedupes_on_persona_horizon_universe_overlay():
    set_persona_candidate_factory(lambda: _demo_candidates() * 3)  # duplicate 3x
    store = FixtureHarnessStore()
    summary = propose_layer3_cadence(store, now_utc_iso())
    assert summary["candidates_total"] == 3
    assert summary["candidates_after_dedupe"] == 1
    assert len(summary["enqueued_jobs"]) == 1


def test_meta_governor_rate_limits_to_3_per_cycle():
    def factory():
        cands = []
        for i, hz in enumerate(["short", "medium", "medium_long", "long"]):
            cands.append(
                {
                    "persona": "quant_residual_analyst",
                    "thesis_family": f"family_{i}",
                    "targeted_horizon": hz,
                    "targeted_universe": "combined_largecap_research_v1",
                    "evidence_refs": [{"kind": "s", "pointer": f"seed://{i}", "summary": "x"}],
                    "confidence": 0.5,
                    "countercase": "ok",
                    "signal_type": "residual_tightening",
                    "intended_overlay_type": "confidence_adjustment",
                    "blocking_reasons": [],
                }
            )
        return cands

    set_persona_candidate_factory(factory)
    store = FixtureHarnessStore()
    summary = propose_layer3_cadence(store, now_utc_iso())
    assert summary["candidates_after_dedupe"] == 3


def test_research_queue_worker_marks_packet_done():
    set_persona_candidate_factory(lambda: _demo_candidates())
    store = FixtureHarnessStore()
    propose_layer3_cadence(store, now_utc_iso())
    claimed = store.claim_next_jobs(queue_class="research_queue", now_utc=now_utc_iso())
    assert len(claimed) == 1
    res = research_queue_worker(store, claimed[0])
    assert res["ok"]


def test_cadence_window_skips_recent_run():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).isoformat()
    assert not should_run_cadence(
        cadence_key="layer3.challenger_cycle",
        last_run_at_utc=last,
        now_utc=now,
    )


def test_layer3_does_not_touch_active_registry_or_overlay():
    set_persona_candidate_factory(lambda: _demo_candidates())
    store = FixtureHarnessStore()
    propose_layer3_cadence(store, now_utc_iso())
    # Store only has research candidate packets; invariant by construction.
    types = {p["packet_type"] for p in store.list_packets()}
    assert types == {"ResearchCandidatePacketV1"}
