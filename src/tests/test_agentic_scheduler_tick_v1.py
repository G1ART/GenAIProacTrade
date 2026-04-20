"""Unit tests for run_one_tick, cadence behaviour, and DLQ transitions (AGH-3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from agentic_harness.contracts.packets_v1 import (
    IngestAlertPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.scheduler.cadences import DEFAULT_CADENCES, should_run_cadence
from agentic_harness.scheduler.tick import (
    LayerCadenceSpec,
    QueueSpec,
    run_one_tick,
)
from agentic_harness.store import FixtureHarnessStore


def _packet(asset: str = "TRGP") -> IngestAlertPacketV1:
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


def test_cadence_skips_when_last_run_within_window():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=1)).isoformat()
    assert not should_run_cadence(
        cadence_key="layer1.transcript_ingest",
        last_run_at_utc=last,
        now_utc=now,
    )
    stale_last = (now - timedelta(hours=7)).isoformat()
    assert should_run_cadence(
        cadence_key="layer1.transcript_ingest",
        last_run_at_utc=stale_last,
        now_utc=now,
    )


def test_default_cadences_have_four_layers():
    assert set(DEFAULT_CADENCES.keys()) == {
        "layer1.transcript_ingest",
        "layer2.coverage_triage",
        "layer3.challenger_cycle",
        "layer4.registry_proposal",
        # AGH v1 Patch 4: validation -> governance scan tick (operator-gated
        # apply; the tick only emits proposals, never mutates active state).
        "layer4.governance_scan",
    }


def test_run_one_tick_invokes_cadence_propose_and_logs():
    store = FixtureHarnessStore()
    calls: list[str] = []

    def propose(s, now_iso):
        calls.append(now_iso)
        return {"enqueued": 0}

    res = run_one_tick(
        store=store,
        layer_cadences=[
            LayerCadenceSpec(cadence_key="layer1.transcript_ingest", propose_fn=propose)
        ],
        queue_specs=[],
    )
    assert res["cadence_decisions"]["layer1.transcript_ingest"] == "ran"
    assert len(calls) == 1
    assert store.last_tick_of_kind("harness_tick") is not None


def test_run_one_tick_respects_cadence_window():
    store = FixtureHarnessStore()
    store.log_tick(tick_kind="cadence:layer1.transcript_ingest", summary={"result": {}})

    def propose(s, now_iso):
        return {"enqueued": 999}

    res = run_one_tick(
        store=store,
        layer_cadences=[
            LayerCadenceSpec(cadence_key="layer1.transcript_ingest", propose_fn=propose)
        ],
        queue_specs=[],
    )
    assert res["cadence_decisions"]["layer1.transcript_ingest"] == "skipped"


def test_dry_run_emits_no_writes():
    store = FixtureHarnessStore()
    res = run_one_tick(
        store=store,
        layer_cadences=[
            LayerCadenceSpec(cadence_key="layer1.transcript_ingest", propose_fn=lambda s, t: {})
        ],
        queue_specs=[],
        dry_run=True,
    )
    assert res["dry_run"] is True
    # no tick log written
    assert store.last_tick_of_kind("harness_tick") is None


def test_worker_ok_marks_job_done():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
        }
    )
    store.enqueue_job(job.model_dump())

    def worker(s, j):
        return {"ok": True, "artifact_ref": "foo"}

    res = run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=worker)],
    )
    assert res["queue_runs"]["ingest_queue"]["done"] == 1
    assert store.get_job(job.job_id)["status"] == "done"


def test_worker_failure_retries_until_dlq():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    now1 = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
            "max_attempts": 2,
            "not_before_utc": now1.isoformat(),
        }
    )
    store.enqueue_job(job.model_dump())

    def bad_worker(s, j):
        # Legacy worker: no `retryable` flag -> scheduler treats as retryable.
        return {"ok": False, "error": "boom"}

    # 1st tick: attempt=1 -> back to enqueued with a 5m backoff.
    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=bad_worker)],
        now=now1,
    )
    row = store.get_job(job.job_id)
    assert row["status"] == "enqueued"
    assert row["attempts"] == 1
    # 2nd tick: advance past backoff so claim_next_jobs sees the job again.
    now2 = now1 + timedelta(minutes=6)
    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=bad_worker)],
        now=now2,
    )
    row = store.get_job(job.job_id)
    assert row["status"] == "dlq"
    assert row["last_error"] == "boom"


def test_worker_exception_treated_as_failure():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
            "max_attempts": 1,
            "not_before_utc": now.isoformat(),
        }
    )
    store.enqueue_job(job.model_dump())

    def raising_worker(s, j):
        raise RuntimeError("network down")

    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=raising_worker)],
        now=now,
    )
    # attempts_so_far==1 and max_attempts==1 -> dlq
    assert store.get_job(job.job_id)["status"] == "dlq"


def test_worker_retryable_false_is_dlq_on_first_failure():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
            "max_attempts": 3,
            "not_before_utc": now.isoformat(),
        }
    )
    store.enqueue_job(job.model_dump())

    def auth_worker(s, j):
        return {"ok": False, "error": "fmp_auth_failed:401", "retryable": False}

    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=auth_worker)],
        now=now,
    )
    row = store.get_job(job.job_id)
    assert row["status"] == "dlq"
    assert row["attempts"] == 1
    assert row["last_error"].startswith("fmp_auth_failed")


def test_worker_retryable_true_gets_exponential_backoff():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    now1 = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
            "max_attempts": 5,
            "not_before_utc": now1.isoformat(),
        }
    )
    store.enqueue_job(job.model_dump())

    def rate_worker(s, j):
        return {"ok": False, "error": "fmp_rate_limited:429", "retryable": True}

    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=rate_worker)],
        now=now1,
    )
    row = store.get_job(job.job_id)
    assert row["status"] == "enqueued"
    # First retry: 5min backoff (300s).
    nbf = datetime.fromisoformat(row["not_before_utc"].replace("Z", "+00:00"))
    delta = (nbf - now1).total_seconds()
    assert 299 <= delta <= 301

    # Claim requires now >= not_before_utc; simulate +6min.
    now2 = now1 + timedelta(minutes=6)
    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=rate_worker)],
        now=now2,
    )
    row = store.get_job(job.job_id)
    assert row["status"] == "enqueued"
    nbf2 = datetime.fromisoformat(row["not_before_utc"].replace("Z", "+00:00"))
    delta2 = (nbf2 - now2).total_seconds()
    # Second retry: 10min backoff.
    assert 599 <= delta2 <= 601


def test_worker_retryable_true_respects_1h_cap():
    store = FixtureHarnessStore()
    pkt = _packet()
    store.upsert_packet(pkt.model_dump())
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    job_dict = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(queue_class="ingest_queue", packet_id=pkt.packet_id),
            "queue_class": "ingest_queue",
            "packet_id": pkt.packet_id,
            "max_attempts": 10,
            "not_before_utc": now.isoformat(),
        }
    ).model_dump()
    # Seed attempts=5 directly so the next claim bumps to 6 and backoff
    # formula (300 * 2^(6-1) = 9600s) exceeds the 1h cap.
    job_dict["attempts"] = 5
    store.enqueue_job(job_dict)

    def rate_worker(s, j):
        return {"ok": False, "error": "fmp_rate_limited:429", "retryable": True}

    run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[QueueSpec(queue_class="ingest_queue", worker_fn=rate_worker)],
        now=now,
    )
    row = store.get_job(job_dict["job_id"])
    assert row["status"] == "enqueued"
    nbf = datetime.fromisoformat(row["not_before_utc"].replace("Z", "+00:00"))
    delta = (nbf - now).total_seconds()
    assert 3599 <= delta <= 3601


def test_run_one_tick_skips_queue_when_no_worker_registered():
    store = FixtureHarnessStore()
    res = run_one_tick(
        store=store,
        layer_cadences=[],
        queue_specs=[],
    )
    assert res["queue_runs"]["ingest_queue"]["reason"] == "no_worker_registered"
