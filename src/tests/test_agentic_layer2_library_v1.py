"""Layer 2 (library integrity triage) tests (AGH-5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agentic_harness.agents import layer2_library
from agentic_harness.agents.layer2_library import (
    coverage_curator_agent,
    integrity_sentinel_agent,
    propose_layer2_cadence,
    quality_queue_worker,
    set_coverage_inspector,
    set_library_inspector,
)
from agentic_harness.scheduler.tick import LayerCadenceSpec, QueueSpec, run_one_tick
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


@pytest.fixture(autouse=True)
def _reset_layer2():
    set_library_inspector(None)
    set_coverage_inspector(None)
    yield
    set_library_inspector(None)
    set_coverage_inspector(None)


def test_integrity_sentinel_emits_one_packet_per_issue():
    set_library_inspector(
        lambda store, now_iso: [
            {
                "check_name": "pit_violation",
                "severity": "medium",
                "offending_refs": ["panel:TRGP:2025Q4"],
                "summary": "PIT asof precedes report_date",
            },
            {
                "check_name": "schema_drift",
                "severity": "high",
                "offending_refs": ["snapshot:aapl:2025Q4"],
                "summary": "issuer_quarter_snapshots missing revenue_ttm",
            },
        ]
    )
    pkts = integrity_sentinel_agent(FixtureHarnessStore(), now_utc_iso())
    assert len(pkts) == 2
    assert {p.payload["check_name"] for p in pkts} == {"pit_violation", "schema_drift"}
    high = next(p for p in pkts if p.payload["severity"] == "high")
    assert high.status == "escalated"


def test_coverage_curator_emits_coverage_gap_packets():
    set_coverage_inspector(
        lambda store, now_iso: [
            {
                "cohort_name": "combined_largecap_research_v1",
                "missing_asset_ids": ["TRGP"],
                "dimension": "transcripts_last_90d",
            }
        ]
    )
    pkts = coverage_curator_agent(FixtureHarnessStore(), now_utc_iso())
    assert len(pkts) == 1
    assert pkts[0].payload["missing_asset_ids"] == ["TRGP"]


def test_severity_medium_or_high_enqueues_quality_queue_job():
    store = FixtureHarnessStore()
    set_library_inspector(
        lambda s, t: [
            {
                "check_name": "pit_violation",
                "severity": "medium",
                "offending_refs": ["panel:TRGP:2025Q4"],
                "summary": "PIT asof precedes report_date",
            },
            {
                "check_name": "missing_coverage",
                "severity": "low",
                "offending_refs": [],
                "summary": "minor",
            },
        ]
    )
    summary = propose_layer2_cadence(store, now_utc_iso())
    assert summary["integrity_packet_count"] == 2
    # Only the medium one (and any coverage gaps) get enqueued.
    assert len(summary["enqueued_quality_jobs"]) == 1
    depth = store.queue_depth()
    assert depth["quality_queue"] == 1


def test_severity_high_marks_escalated_packet_status():
    store = FixtureHarnessStore()
    set_library_inspector(
        lambda s, t: [
            {
                "check_name": "schema_drift",
                "severity": "high",
                "offending_refs": ["panel:TRGP:2025Q4"],
                "summary": "drift",
            }
        ]
    )
    summary = propose_layer2_cadence(store, now_utc_iso())
    assert len(summary["escalated_packet_ids"]) == 1
    pid = summary["escalated_packet_ids"][0]
    assert store.get_packet(pid)["status"] == "escalated"


def test_quality_queue_worker_marks_triage_status():
    store = FixtureHarnessStore()
    set_library_inspector(
        lambda s, t: [
            {
                "check_name": "pit_violation",
                "severity": "medium",
                "offending_refs": ["panel:TRGP:2025Q4"],
                "summary": "PIT asof precedes report_date",
            }
        ]
    )
    propose_layer2_cadence(store, now_utc_iso())
    claimed = store.claim_next_jobs(queue_class="quality_queue", now_utc=now_utc_iso())
    assert len(claimed) == 1
    res = quality_queue_worker(store, claimed[0])
    assert res["ok"]
    assert store.get_packet(res["triaged_packet_id"])["status"] == "escalated"


def test_run_one_tick_wires_layer2_end_to_end():
    store = FixtureHarnessStore()
    set_library_inspector(
        lambda s, t: [
            {
                "check_name": "stale_data",
                "severity": "medium",
                "offending_refs": ["panel:TRGP:2025Q3"],
                "summary": "stale > 45d",
            }
        ]
    )
    out = run_one_tick(
        store=store,
        layer_cadences=[
            LayerCadenceSpec(
                cadence_key="layer2.coverage_triage", propose_fn=propose_layer2_cadence
            )
        ],
        queue_specs=[QueueSpec(queue_class="quality_queue", worker_fn=quality_queue_worker)],
    )
    assert out["queue_runs"]["quality_queue"]["done"] == 1
