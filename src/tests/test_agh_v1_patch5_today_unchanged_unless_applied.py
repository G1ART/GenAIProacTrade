"""AGH v1 Patch 5 — non-regression: Today never mutates from the Research/Sandbox path.

This is an AC-5 guard: after Patch 5, the Research Ask + bounded
sandbox pipelines must not directly mutate the active registry or the
Today surface. Only the Patch 3 ``RegistryPatchAppliedPacketV1`` path
is allowed to flip ``active_artifact_id``.

These tests exercise the scenario end-to-end in a fixture harness:

    1. Snapshot the brain bundle's ``(registry_entry, active_artifact)``.
    2. Enqueue + run a bounded ``validation_rerun`` sandbox.
    3. Confirm:
        * the bundle is unchanged,
        * no ``RegistryPatchAppliedPacketV1`` was emitted,
        * the Today spectrum still points at the original
          ``active_artifact_id``,
        * the Today detail payload still reports the same
          ``active_artifact_id`` on ``registry_surface_v1``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_harness.agents import layer3_sandbox_executor_v1 as sbx
from agentic_harness.store import FixtureHarnessStore
from metis_brain.bundle import try_load_brain_bundle_v0
from phase47_runtime.today_spectrum import build_today_spectrum_payload


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_worker_does_not_change_today_active_artifact(monkeypatch):
    # Force registry-backed today surface so the regression scenario
    # exercises a real active_artifact_id (the conftest default flips
    # this to ``seed`` for other tests).
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    bundle_before, _ = try_load_brain_bundle_v0(REPO_ROOT)
    if bundle_before is None:
        pytest.skip("brain bundle not loadable in this env")

    sp_before = build_today_spectrum_payload(
        repo_root=REPO_ROOT, horizon="short", lang="ko"
    )
    if not sp_before.get("ok"):
        pytest.skip("today spectrum not buildable")
    surface_before = sp_before.get("registry_surface_v1") or {}
    rid = surface_before.get("registry_entry_id")
    active_before = surface_before.get("active_artifact_id")
    if not rid or not active_before:
        pytest.skip("no active registry_entry for regression test")

    store = FixtureHarnessStore()
    sbx.set_sandbox_validation_rerun_runner(
        lambda _s, _c: {"run_id": "fvr_no_mutate_1"}
    )
    sbx.set_sandbox_client_factory(lambda: object())

    enq = sbx.enqueue_sandbox_request(
        store,
        request_id="sbx_regression_1",
        sandbox_kind="validation_rerun",
        registry_entry_id=rid,
        horizon="short",
        target_spec={
            "factor_name": "earnings_quality_composite",
            "universe_name": str(surface_before.get("universe") or ""),
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_regression_1"
        ],
    )
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=10)
    target = next(
        (j for j in jobs if j.get("packet_id") == enq["request_packet_id"]),
        None,
    )
    assert target is not None
    out = sbx.sandbox_queue_worker(store, dict(target))
    assert out["outcome"] == "completed"

    bundle_after, _ = try_load_brain_bundle_v0(REPO_ROOT)
    assert bundle_after is not None
    assert bundle_after.model_dump() == bundle_before.model_dump(), (
        "brain bundle must not mutate from sandbox path"
    )

    applied_packets = store.list_packets(
        packet_type="RegistryPatchAppliedPacketV1", limit=50
    )
    assert list(applied_packets) == [], (
        "sandbox executor must NEVER emit RegistryPatchAppliedPacketV1"
    )

    sp_after = build_today_spectrum_payload(
        repo_root=REPO_ROOT, horizon="short", lang="ko"
    )
    surface_after = sp_after.get("registry_surface_v1") or {}
    assert surface_after.get("active_artifact_id") == active_before
    assert surface_after.get("registry_entry_id") == rid
