"""AGH v1 Patch 5 — Layer 3 sandbox executor + worker tests.

Covers the bounded ``validation_rerun`` closed-loop (Patch 5 §C2):

    1. ``enqueue_sandbox_request`` creates a ``SandboxRequestPacketV1``
       and a ``sandbox_queue`` job pointing at it.
    2. Running the worker with a stub runner emits a
       ``SandboxResultPacketV1`` with outcome=``completed`` citing the
       request + producing the returned ``factor_validation_run_id``.
    3. The worker is idempotent — a second run on the same job is a
       ``skipped`` / ``result_already_emitted`` no-op.
    4. Unsupported ``sandbox_kind`` lands as
       ``rejected_kind_not_allowed``.
    5. Missing runner + missing client factory lands as
       ``blocked_insufficient_inputs`` rather than silently succeeding.
    6. Active-registry guarantee: the brain bundle file is not mutated
       by the worker. (We assert ``SandboxResultPacketV1.payload`` is
       packet-only; bundle mutations are impossible because the worker
       has no bundle writer.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_harness.agents import layer3_sandbox_executor_v1 as sbx
from agentic_harness.store import FixtureHarnessStore


def _request_kwargs(**over) -> dict:
    base = dict(
        request_id="sbx_req_exec_1",
        sandbox_kind="validation_rerun",
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        target_spec={
            "factor_name": "earnings_quality_composite",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_demo_1",
        ],
    )
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _clean_sandbox_hooks():
    # Always start from a clean slate and restore after each test.
    prev_runner = sbx.get_sandbox_validation_rerun_runner()
    prev_factory = sbx.get_sandbox_client_factory()
    sbx.set_sandbox_validation_rerun_runner(None)
    sbx.set_sandbox_client_factory(None)
    yield
    sbx.set_sandbox_validation_rerun_runner(prev_runner)
    sbx.set_sandbox_client_factory(prev_factory)


def test_enqueue_emits_request_packet_and_sandbox_queue_job():
    store = FixtureHarnessStore()
    out = sbx.enqueue_sandbox_request(store, **_request_kwargs())
    assert out["ok"] is True
    req_id = out["request_packet_id"]
    assert req_id.startswith("pkt_")
    req = store.get_packet(req_id)
    assert req and req["packet_type"] == "SandboxRequestPacketV1"
    # job on sandbox_queue
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=10)
    assert any(j.get("packet_id") == req_id for j in jobs)


def test_worker_completes_and_emits_result_with_produced_refs():
    store = FixtureHarnessStore()

    def stub_runner(target_spec, _client):
        return {
            "run_id": "fvr_sandbox_done_1",
            "status": "completed",
            "factors_ok": 1,
            "factors_failed": 0,
        }

    sbx.set_sandbox_validation_rerun_runner(stub_runner)
    sbx.set_sandbox_client_factory(lambda: object())

    enq = sbx.enqueue_sandbox_request(store, **_request_kwargs())
    req_id = enq["request_packet_id"]
    job = store.list_jobs(queue_class="sandbox_queue", limit=10)[0]

    out = sbx.sandbox_queue_worker(store, dict(job))
    assert out["ok"] is True
    assert out["outcome"] == "completed"
    result_id = out["result_packet_id"]
    res = store.get_packet(result_id)
    assert res is not None
    p = res["payload"]
    assert p["outcome"] == "completed"
    assert p["cited_request_packet_id"] == req_id
    assert any(
        r.get("kind") == "factor_validation_run_id"
        and r.get("id") == "fvr_sandbox_done_1"
        for r in p["produced_refs"]
    )


def test_worker_is_idempotent_second_run_is_skipped():
    store = FixtureHarnessStore()
    sbx.set_sandbox_validation_rerun_runner(lambda _s, _c: {"run_id": "fvr_idem"})
    sbx.set_sandbox_client_factory(lambda: object())

    sbx.enqueue_sandbox_request(store, **_request_kwargs())
    job = store.list_jobs(queue_class="sandbox_queue", limit=10)[0]
    first = sbx.sandbox_queue_worker(store, dict(job))
    second = sbx.sandbox_queue_worker(store, dict(job))
    assert first["outcome"] == "completed"
    assert second.get("skipped") is True
    assert second.get("result_packet_id") == first["result_packet_id"]


def test_worker_rejects_disallowed_sandbox_kind_via_stored_packet():
    store = FixtureHarnessStore()
    sbx.set_sandbox_validation_rerun_runner(lambda _s, _c: {"run_id": "ignored"})
    sbx.set_sandbox_client_factory(lambda: object())

    # enqueue_sandbox_request itself rejects — but we must also guard the
    # worker path when a request packet with an unsupported sandbox_kind
    # somehow lands in the store (e.g. older schema). Simulate by
    # manually writing a SandboxRequestPacketV1 whose payload carries a
    # still-allowed kind, then overriding sandbox_kind in-store BEFORE
    # running the worker.
    enq = sbx.enqueue_sandbox_request(store, **_request_kwargs())
    req_id = enq["request_packet_id"]
    req_row = dict(store.get_packet(req_id) or {})
    req_row["payload"] = {
        **req_row["payload"],
        "sandbox_kind": "evidence_refresh",
    }
    store.upsert_packet(req_row)
    job = store.list_jobs(queue_class="sandbox_queue", limit=10)[0]
    out = sbx.sandbox_queue_worker(store, dict(job))
    assert out["outcome"] == "rejected_kind_not_allowed"
    res = store.get_packet(out["result_packet_id"])
    assert res and res["payload"]["outcome"] == "rejected_kind_not_allowed"


def test_worker_blocks_when_no_runner_and_no_client_factory():
    store = FixtureHarnessStore()
    # Neither runner nor client factory installed (autouse fixture).
    sbx.enqueue_sandbox_request(store, **_request_kwargs())
    job = store.list_jobs(queue_class="sandbox_queue", limit=10)[0]
    out = sbx.sandbox_queue_worker(store, dict(job))
    assert out["outcome"] == "blocked_insufficient_inputs"
    assert out["blocking_reasons"], "must include a non-empty blocking reason"


def test_worker_bundle_is_not_mutated_by_executor():
    # The executor has no bundle path / writer. This test documents the
    # invariant by asserting the brain bundle file mtime is unchanged
    # across a worker run.
    repo_root = Path(__file__).resolve().parents[2]
    bundle_path = repo_root / "data" / "mvp" / "metis_brain_bundle_v0.json"
    if not bundle_path.is_file():  # hermetic envs may not seed the bundle
        pytest.skip("brain bundle file not present in this environment")
    before = bundle_path.stat().st_mtime_ns

    store = FixtureHarnessStore()
    sbx.set_sandbox_validation_rerun_runner(
        lambda _s, _c: {"run_id": "fvr_non_mutating_1"}
    )
    sbx.set_sandbox_client_factory(lambda: object())
    sbx.enqueue_sandbox_request(store, **_request_kwargs())
    job = store.list_jobs(queue_class="sandbox_queue", limit=10)[0]
    out = sbx.sandbox_queue_worker(store, dict(job))
    assert out["outcome"] == "completed"

    after = bundle_path.stat().st_mtime_ns
    assert before == after, "sandbox executor must NOT mutate the brain bundle"
