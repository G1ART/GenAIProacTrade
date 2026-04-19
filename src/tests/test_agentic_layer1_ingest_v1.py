"""Layer 1 (proactive ingest) tests (AGH-4).

All tests drive the fixture store and inject a mock transcript fetcher, so
there is no network access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from agentic_harness.agents import layer1_ingest
from agentic_harness.agents.layer1_ingest import (
    SOURCE_FAMILY_TRANSCRIPTS,
    event_trigger_agent,
    ingest_coordinator_agent,
    ingest_queue_worker,
    propose_layer1_cadence,
    set_stale_asset_provider,
    set_transcript_fetcher,
    source_scout_agent,
)
from agentic_harness.scheduler.tick import LayerCadenceSpec, QueueSpec, run_one_tick
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


@pytest.fixture(autouse=True)
def _reset_injections():
    set_stale_asset_provider(None)
    set_transcript_fetcher(None)
    yield
    set_stale_asset_provider(None)
    set_transcript_fetcher(None)


def _fresh_iso(now: datetime, hours_ago: int) -> str:
    return (now - timedelta(hours=hours_ago)).isoformat()


def test_source_scout_flags_stale_but_not_fresh_assets():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)

    def provider(store, now_iso):
        return [
            {
                "asset_id": "TRGP",
                "last_fetched_at_utc": _fresh_iso(now, hours_ago=96),
                "expected_freshness_hours": 72,
            },
            {
                "asset_id": "AAPL",
                "last_fetched_at_utc": _fresh_iso(now, hours_ago=1),
                "expected_freshness_hours": 72,
            },
            {
                "asset_id": "NVDA",
                "last_fetched_at_utc": "",  # never fetched -> stale
                "expected_freshness_hours": 72,
            },
        ]

    set_stale_asset_provider(provider)
    store = FixtureHarnessStore()
    stale = source_scout_agent(store, now.isoformat())
    assert {x["asset_id"] for x in stale} == {"TRGP", "NVDA"}


def test_event_trigger_agent_builds_valid_packet():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    pkt = event_trigger_agent(
        candidate={
            "asset_id": "TRGP",
            "last_fetched_at_utc": _fresh_iso(now, 96),
            "expected_freshness_hours": 72,
        },
        now_iso=now.isoformat(),
    )
    assert pkt.packet_type == "EventTriggerPacketV1"
    assert pkt.payload["asset_id"] == "TRGP"
    assert pkt.payload["trigger_kind"] == "earnings_transcript_stale"


def test_ingest_coordinator_enqueues_job_on_ingest_queue():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    store = FixtureHarnessStore()
    trigger = event_trigger_agent(
        candidate={
            "asset_id": "TRGP",
            "last_fetched_at_utc": "",
            "expected_freshness_hours": 72,
        },
        now_iso=now.isoformat(),
    )
    res = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now.isoformat())
    assert res is not None
    assert store.queue_depth()["ingest_queue"] == 1
    assert store.get_packet(res["alert_packet_id"]) is not None


def test_ingest_coordinator_idempotent_within_same_tick():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    store = FixtureHarnessStore()
    trigger = event_trigger_agent(
        candidate={
            "asset_id": "TRGP",
            "last_fetched_at_utc": "",
            "expected_freshness_hours": 72,
        },
        now_iso=now.isoformat(),
    )
    first = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now.isoformat())
    second = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now.isoformat())
    assert first is not None
    assert second is None  # dedupe kicks in on same packet_id active job
    assert store.queue_depth()["ingest_queue"] == 1


def test_propose_layer1_cadence_drives_end_to_end_enqueue():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)

    def provider(store, now_iso):
        return [
            {"asset_id": "TRGP", "last_fetched_at_utc": "", "expected_freshness_hours": 72}
        ]

    set_stale_asset_provider(provider)
    store = FixtureHarnessStore()
    summary = propose_layer1_cadence(store, now.isoformat())
    assert summary["stale_asset_count"] == 1
    assert summary["enqueued"] == 1


def test_ingest_queue_worker_ok_path_emits_source_artifact_packet():
    store = FixtureHarnessStore()

    def provider(s, now_iso):
        return [{"asset_id": "TRGP", "last_fetched_at_utc": "", "expected_freshness_hours": 72}]

    def fetcher(job_meta):
        return {
            "ok": True,
            "artifact_ref": "fmp://transcripts/TRGP/2026Q1",
            "fetched_at_utc": "2026-04-17T12:05:00+00:00",
            "provenance_refs": ["fmp://transcripts/TRGP/2026Q1"],
        }

    set_stale_asset_provider(provider)
    set_transcript_fetcher(fetcher)
    propose_layer1_cadence(store, now_utc_iso())
    claimed = store.claim_next_jobs(queue_class="ingest_queue", now_utc=now_utc_iso())
    assert len(claimed) == 1
    res = ingest_queue_worker(store, claimed[0])
    assert res["ok"]
    sa = store.get_packet(res["source_artifact_packet_id"])
    assert sa["packet_type"] == "SourceArtifactPacketV1"
    assert sa["payload"]["fetch_outcome"] == "ok"


def test_ingest_queue_worker_failure_propagates_for_dlq():
    store = FixtureHarnessStore()

    def provider(s, now_iso):
        return [{"asset_id": "TRGP", "last_fetched_at_utc": "", "expected_freshness_hours": 72}]

    def flaky(job_meta):
        return {"ok": False, "error": "http_503"}

    set_stale_asset_provider(provider)
    set_transcript_fetcher(flaky)
    propose_layer1_cadence(store, now_utc_iso())
    claimed = store.claim_next_jobs(queue_class="ingest_queue", now_utc=now_utc_iso())
    res = ingest_queue_worker(store, claimed[0])
    assert res["ok"] is False
    assert "http_503" in res["error"]


def test_full_vertical_path_through_scheduler_tick():
    store = FixtureHarnessStore()

    def provider(s, now_iso):
        return [{"asset_id": "TRGP", "last_fetched_at_utc": "", "expected_freshness_hours": 72}]

    def fetcher(job_meta):
        return {
            "ok": True,
            "artifact_ref": "fmp://transcripts/TRGP/2026Q1",
            "provenance_refs": ["fmp://transcripts/TRGP/2026Q1"],
        }

    set_stale_asset_provider(provider)
    set_transcript_fetcher(fetcher)

    # First tick: cadence seeds the alert, worker drains it in the same tick.
    summary = run_one_tick(
        store=store,
        layer_cadences=[
            LayerCadenceSpec(
                cadence_key="layer1.transcript_ingest",
                propose_fn=propose_layer1_cadence,
            )
        ],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=ingest_queue_worker)],
    )
    assert summary["layer_summaries"]["layer1.transcript_ingest"]["enqueued"] == 1
    assert summary["queue_runs"]["ingest_queue"]["done"] == 1
    # The Today registry / bundle were never mutated.
    # (Fixture store doesn't carry those tables; production code is the
    # contract: layer 1 never touches active truth.)
    sa_packets = store.list_packets(packet_type="SourceArtifactPacketV1")
    assert len(sa_packets) == 1
