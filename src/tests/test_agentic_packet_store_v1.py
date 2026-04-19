"""Unit tests for the agentic harness store layer (AGH-2).

These tests drive the fixture store. The Supabase store shares the exact same
``HarnessStoreProtocol`` shape so the invariants tested here - idempotency,
status transitions, claim semantics - are contract-level and portable.
"""

from __future__ import annotations

import pytest

from agentic_harness.contracts.packets_v1 import (
    IngestAlertPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store import FixtureHarnessStore, HarnessStoreProtocol, StoreError
from agentic_harness.store.protocol import now_utc_iso


def _build_ingest_packet(asset: str = "TRGP") -> IngestAlertPacketV1:
    return IngestAlertPacketV1.model_validate(
        {
            "packet_id": deterministic_packet_id(
                packet_type="IngestAlertPacketV1",
                created_by_agent="source_scout_agent",
                target_scope={"asset_id": asset},
            ),
            "packet_type": "IngestAlertPacketV1",
            "target_layer": "layer1_ingest",
            "created_by_agent": "source_scout_agent",
            "target_scope": {"asset_id": asset},
            "provenance_refs": [f"registry://today/{asset}"],
            "confidence": 0.7,
            "payload": {
                "source_family": "earnings_transcript",
                "trigger_kind": "earnings_transcript_stale",
                "asset_ids": [asset],
            },
        }
    )


def test_fixture_store_conforms_to_protocol():
    s = FixtureHarnessStore()
    assert isinstance(s, HarnessStoreProtocol)


def test_packet_upsert_and_fetch_round_trip():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    stored = s.upsert_packet(pkt.model_dump())
    assert stored["packet_id"] == pkt.packet_id
    fetched = s.get_packet(pkt.packet_id)
    assert fetched is not None
    assert fetched["packet_type"] == "IngestAlertPacketV1"
    assert fetched["payload"]["asset_ids"] == ["TRGP"]


def test_set_packet_status_persists():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    s.set_packet_status(pkt.packet_id, "enqueued")
    assert s.get_packet(pkt.packet_id)["status"] == "enqueued"


def test_list_packets_filters_by_layer_and_status():
    s = FixtureHarnessStore()
    s.upsert_packet(_build_ingest_packet("TRGP").model_dump())
    s.upsert_packet(_build_ingest_packet("AAPL").model_dump())
    assert len(s.list_packets(target_layer="layer1_ingest")) == 2
    assert len(s.list_packets(target_layer="layer4_governance")) == 0


def test_count_packets_by_layer():
    s = FixtureHarnessStore()
    s.upsert_packet(_build_ingest_packet("TRGP").model_dump())
    s.upsert_packet(_build_ingest_packet("AAPL").model_dump())
    counts = s.count_packets_by_layer()
    assert counts.get("layer1_ingest") == 2


def test_enqueue_and_claim_transitions_to_running():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    claimed = s.claim_next_jobs(queue_class="ingest_queue", now_utc=now_utc_iso(), max_jobs=5)
    assert len(claimed) == 1
    assert claimed[0]["status"] == "running"
    assert claimed[0]["attempts"] == 1


def test_enqueue_rejects_duplicate_active_job_for_same_packet():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    dup = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="ingest_queue", packet_id=pkt.packet_id, salt="dup"
            ),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    with pytest.raises(StoreError):
        s.enqueue_job(dup.model_dump())


def test_enqueue_rejects_unknown_packet_id():
    s = FixtureHarnessStore()
    with pytest.raises(StoreError):
        s.enqueue_job(
            {
                "job_id": "job_orphan",
                "queue_class": "ingest_queue",
                "packet_id": "pkt_missing",
                "status": "enqueued",
                "attempts": 0,
                "max_attempts": 3,
            }
        )


def test_mark_job_result_done_after_claim():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    s.claim_next_jobs(queue_class="ingest_queue", now_utc=now_utc_iso())
    s.mark_job_result(job_id=job.job_id, status="done", result_json={"artifact_ref": "foo"})
    row = s.get_job(job.job_id)
    assert row["status"] == "done"
    assert row["result_json"] == {"artifact_ref": "foo"}


def test_dlq_transition_keeps_row_retrievable():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    s.mark_job_result(
        job_id=job.job_id,
        status="dlq",
        last_error="transcript adapter returned 503",
        increment_attempts=True,
    )
    row = s.get_job(job.job_id)
    assert row["status"] == "dlq"
    assert row["last_error"] == "transcript adapter returned 503"
    assert row["attempts"] == 1


def test_after_job_done_can_enqueue_same_packet_again():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    j1 = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(j1.model_dump())
    s.mark_job_result(job_id=j1.job_id, status="done")
    j2 = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="ingest_queue", packet_id=pkt.packet_id, salt="cycle2"
            ),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(j2.model_dump())
    assert len(s.list_jobs(queue_class="ingest_queue")) == 2


def test_queue_depth_only_counts_enqueued():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    j1 = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(j1.model_dump())
    depth = s.queue_depth()
    assert depth["ingest_queue"] == 1
    assert depth["governance_queue"] == 0
    s.claim_next_jobs(queue_class="ingest_queue", now_utc=now_utc_iso())
    assert s.queue_depth()["ingest_queue"] == 0


def test_mark_job_result_enqueued_applies_next_not_before_utc():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    s.mark_job_result(
        job_id=job.job_id,
        status="enqueued",
        last_error="fmp_rate_limited:429",
        next_not_before_utc="2099-01-01T00:00:00+00:00",
    )
    row = s.get_job(job.job_id)
    assert row["status"] == "enqueued"
    assert row["not_before_utc"] == "2099-01-01T00:00:00+00:00"


def test_mark_job_result_ignores_next_not_before_utc_for_non_enqueued_status():
    s = FixtureHarnessStore()
    pkt = _build_ingest_packet()
    s.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    s.enqueue_job(job.model_dump())
    original_nbf = s.get_job(job.job_id)["not_before_utc"]
    s.mark_job_result(
        job_id=job.job_id,
        status="dlq",
        last_error="auth",
        next_not_before_utc="2099-01-01T00:00:00+00:00",
    )
    row = s.get_job(job.job_id)
    assert row["status"] == "dlq"
    # not_before_utc should be unchanged because status != 'enqueued'.
    assert row["not_before_utc"] == original_nbf


def test_log_tick_and_last_tick_of_kind():
    s = FixtureHarnessStore()
    t = s.log_tick(tick_kind="harness_tick", summary={"jobs_run": 3})
    assert t["tick_id"]
    assert s.last_tick_of_kind("harness_tick")["summary"]["jobs_run"] == 3
    assert s.last_tick_of_kind("not_a_kind") is None
