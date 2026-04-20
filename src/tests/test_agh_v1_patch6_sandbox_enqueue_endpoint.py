"""AGH v1 Patch 6 — E1 POST /api/sandbox/enqueue thin endpoint.

Gates the UI "Enqueue via UI (operator-gated)" button behind the
``METIS_HARNESS_UI_INVOKE_ENABLED`` env var. The endpoint never
autonomously runs the sandbox worker; it delegates to
``enqueue_sandbox_request`` and reports the ``harness-tick`` CLI hint.
"""

from __future__ import annotations

import pytest

from agentic_harness.agents import layer3_sandbox_executor_v1 as sbx
from agentic_harness.store import FixtureHarnessStore
from phase47_runtime import routes as runtime_routes
from phase47_runtime.routes import api_sandbox_enqueue_v1


@pytest.fixture(autouse=True)
def _reset_sandbox_hooks():
    prev_runner = sbx.get_sandbox_validation_rerun_runner()
    prev_factory = sbx.get_sandbox_client_factory()
    sbx.set_sandbox_validation_rerun_runner(None)
    sbx.set_sandbox_client_factory(None)
    yield
    sbx.set_sandbox_validation_rerun_runner(prev_runner)
    sbx.set_sandbox_client_factory(prev_factory)


@pytest.fixture
def ui_invoke_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METIS_HARNESS_UI_INVOKE_ENABLED", "1")


@pytest.fixture
def ui_invoke_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("METIS_HARNESS_UI_INVOKE_ENABLED", raising=False)


@pytest.fixture
def fixture_store(monkeypatch: pytest.MonkeyPatch) -> FixtureHarnessStore:
    store = FixtureHarnessStore()
    monkeypatch.setattr(
        runtime_routes, "_build_harness_store_for_api", lambda use_fixture=False: store
    )
    return store


def _valid_body(**overrides):
    base = {
        "sandbox_kind": "validation_rerun",
        "registry_entry_id": "reg_short_demo_v0",
        "horizon": "short",
        "target_spec": {
            "factor_name": "earnings_quality_composite",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        "rationale": "UI operator-triggered rerun to tighten residual confidence.",
        "cited_evidence_packet_ids": ["ValidationPromotionEvaluationV1:ev_demo_1"],
    }
    base.update(overrides)
    return base


def test_returns_403_when_ui_invoke_disabled(ui_invoke_disabled) -> None:
    status, body = api_sandbox_enqueue_v1(state=None, body=_valid_body())
    assert status == 403
    assert body["ok"] is False
    assert body["error"] == "ui_invoke_disabled"
    assert "METIS_HARNESS_UI_INVOKE_ENABLED" in body["hint"]


def test_returns_400_on_missing_required_fields(ui_invoke_enabled) -> None:
    status, body = api_sandbox_enqueue_v1(state=None, body={"sandbox_kind": "validation_rerun"})
    assert status == 400
    assert body["ok"] is False
    assert body["error"].startswith("missing_fields:")


def test_returns_400_on_unknown_sandbox_kind(ui_invoke_enabled) -> None:
    status, body = api_sandbox_enqueue_v1(
        state=None, body=_valid_body(sandbox_kind="residual_review")
    )
    assert status == 400
    assert body["ok"] is False
    assert "sandbox_kind_not_allowed" in body["error"]


def test_returns_400_on_empty_cited_evidence(ui_invoke_enabled) -> None:
    status, body = api_sandbox_enqueue_v1(
        state=None, body=_valid_body(cited_evidence_packet_ids=[])
    )
    assert status == 400
    assert "cited_evidence_packet_ids" in body["error"]


def test_returns_400_when_rationale_missing(ui_invoke_enabled) -> None:
    status, body = api_sandbox_enqueue_v1(state=None, body=_valid_body(rationale=""))
    assert status == 400
    assert "rationale" in body["error"]


def test_returns_400_on_incomplete_target_spec(ui_invoke_enabled) -> None:
    bad_target = {"factor_name": "f1"}
    status, body = api_sandbox_enqueue_v1(state=None, body=_valid_body(target_spec=bad_target))
    assert status == 400
    assert body["error"].startswith("target_spec_missing:")


def test_happy_path_enqueues_and_returns_cli_hint(
    ui_invoke_enabled, fixture_store: FixtureHarnessStore
) -> None:
    status, body = api_sandbox_enqueue_v1(state=None, body=_valid_body(request_id="ui-op-req-1"))
    assert status == 200, body
    assert body["ok"] is True
    assert body["contract"] == "AGH_V1_SANDBOX_ENQUEUE_V1"
    assert body["cli_hint"] == "harness-tick --queue sandbox_queue"
    req_id = body["request_packet_id"]
    assert req_id and req_id.startswith("pkt_")

    # The endpoint must delegate to enqueue_sandbox_request, which creates
    # a SandboxRequestPacketV1 and a sandbox_queue job pointed at it.
    packet = fixture_store.get_packet(req_id)
    assert packet is not None
    assert packet["packet_type"] == "SandboxRequestPacketV1"
    jobs = fixture_store.list_jobs(queue_class="sandbox_queue", limit=5)
    assert any(j.get("packet_id") == req_id for j in jobs)

    # The endpoint must NOT execute the worker. The only sandbox packet
    # should be the request — no SandboxResultPacketV1 may exist yet.
    for pid, pkt in fixture_store._packets.items():  # type: ignore[attr-defined]
        assert pkt["packet_type"] != "SandboxResultPacketV1", (
            f"endpoint autonomously executed worker: {pid}"
        )
