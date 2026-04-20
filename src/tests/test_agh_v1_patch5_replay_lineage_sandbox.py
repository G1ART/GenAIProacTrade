"""AGH v1 Patch 5 — replay lineage / sandbox followups tests.

Covers ``api_governance_lineage_for_registry_entry`` after the Patch 5
extension:

    1. Sandbox requests + results scoped to the cited
       ``registry_entry_id`` / ``horizon`` appear in
       ``sandbox_followups`` with matching ``{request, result}`` pairs.
    2. Counters ``total_sandbox_requests / _completed / _blocked``
       match the pairs.
    3. Requests for other registry_entries are NOT surfaced (no
       cross-entry leakage).
    4. Requests without a result packet still appear (with
       ``result=None``) so the UI can show "still pending" honestly.
"""

from __future__ import annotations

from agentic_harness.agents import layer3_sandbox_executor_v1 as sbx
from agentic_harness.store import FixtureHarnessStore
from phase47_runtime.traceability_replay import (
    api_governance_lineage_for_registry_entry,
)


def _seed_request_and_result(
    store,
    *,
    registry_entry_id: str = "reg_short_demo_v0",
    horizon: str = "short",
    request_id: str = "sbx_rep_1",
    run_id: str = "fvr_rep_done_1",
):
    sbx.set_sandbox_validation_rerun_runner(lambda _s, _c: {"run_id": run_id})
    sbx.set_sandbox_client_factory(lambda: object())
    out = sbx.enqueue_sandbox_request(
        store,
        request_id=request_id,
        sandbox_kind="validation_rerun",
        registry_entry_id=registry_entry_id,
        horizon=horizon,
        target_spec={
            "factor_name": "earnings_quality_composite",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_rep_1"
        ],
    )
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=10)
    target = next(
        (j for j in jobs if j.get("packet_id") == out["request_packet_id"]),
        None,
    )
    assert target is not None
    sbx.sandbox_queue_worker(store, dict(target))
    return out["request_packet_id"]


def test_sandbox_followups_pair_request_with_result():
    store = FixtureHarnessStore()
    req_id = _seed_request_and_result(store)
    resp = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )
    assert resp["ok"] is True
    fups = resp["sandbox_followups"]
    assert len(fups) == 1
    row = fups[0]
    assert row["request"]["packet_id"] == req_id
    assert row["result"] is not None
    assert row["result"]["payload"]["outcome"] == "completed"
    assert resp["summary"]["total_sandbox_requests"] == 1
    assert resp["summary"]["total_sandbox_completed"] == 1
    assert resp["summary"]["total_sandbox_blocked"] == 0


def test_sandbox_followups_exclude_other_registry_entries():
    store = FixtureHarnessStore()
    _seed_request_and_result(
        store,
        registry_entry_id="reg_short_demo_v0",
        request_id="sbx_rep_scope_1",
        run_id="fvr_rep_scope_1",
    )
    _seed_request_and_result(
        store,
        registry_entry_id="reg_medium_demo_v0",
        horizon="medium",
        request_id="sbx_rep_scope_2",
        run_id="fvr_rep_scope_2",
    )
    resp = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )
    assert len(resp["sandbox_followups"]) == 1
    assert (
        resp["sandbox_followups"][0]["request"]["payload"]["registry_entry_id"]
        == "reg_short_demo_v0"
    )


def test_sandbox_followups_include_pending_requests_without_result():
    store = FixtureHarnessStore()
    # Neither runner nor client factory -> worker blocks (produces result).
    # So to get a "no result" state, enqueue the request but do NOT run
    # the worker at all.
    sbx.set_sandbox_validation_rerun_runner(None)
    sbx.set_sandbox_client_factory(None)
    sbx.enqueue_sandbox_request(
        store,
        request_id="sbx_rep_pending_1",
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
        cited_evidence_packet_ids=["ValidationPromotionEvaluationV1:ev_rep_pending"],
    )
    resp = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )
    assert resp["summary"]["total_sandbox_requests"] == 1
    # No result packet yet (the worker never ran).
    assert resp["sandbox_followups"][0]["result"] is None
