"""AGH v1 Patch 5 — SandboxRequestPacketV1 / SandboxResultPacketV1 / queue / migration vocabulary tests.

Guards the contracts the rest of the Research-Ask / Sandbox closure is
built on. These tests enforce:

    1. ``SANDBOX_KINDS`` / ``SANDBOX_REQUEST_ACTORS`` /
       ``SANDBOX_RESULT_OUTCOMES`` remain the narrow, deterministic
       enums the rest of the harness relies on (Patch 5 explicitly ships
       ``validation_rerun`` as the only supported closed-loop kind).
    2. ``SandboxRequestPacketV1`` rejects unsupported sandbox_kind
       values, enforces non-empty ``target_spec`` for
       ``validation_rerun``, and preserves packet base invariants.
    3. ``SandboxResultPacketV1`` rejects invalid outcomes, demands
       ``blocking_reasons`` when outcome is not ``completed``, and
       re-emits deterministic packet ids.
    4. ``sandbox_queue`` is present in ``QUEUE_CLASSES`` exactly once.
    5. Both sandbox packet types appear in ``PACKET_TYPES`` +
       ``PACKET_TYPE_TO_CLASS``.
    6. The Supabase migration 20260420100000 whitelists them in the CK
       constraints (source-of-truth regression guard).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_harness.contracts.packets_v1 import (
    PACKET_TYPE_TO_CLASS,
    PACKET_TYPES,
    SANDBOX_KINDS,
    SANDBOX_REQUEST_ACTORS,
    SANDBOX_RESULT_OUTCOMES,
    SandboxRequestPacketV1,
    SandboxResultPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QUEUE_CLASSES


def _req_kwargs(**over) -> dict:
    base = {
        "packet_id": deterministic_packet_id(
            packet_type="SandboxRequestPacketV1",
            created_by_agent="operator",
            target_scope={"registry_entry_id": "reg_short_demo_v0"},
        ),
        "packet_type": "SandboxRequestPacketV1",
        "target_layer": "layer3_research",
        "created_by_agent": "operator",
        "target_scope": {"registry_entry_id": "reg_short_demo_v0"},
        "provenance_refs": ["registry://reg_short_demo_v0"],
        "confidence": 0.7,
        "blocking_reasons": [],
        "payload": {
            "request_id": "sbx_req_demo_1",
            "sandbox_kind": "validation_rerun",
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
            "target_spec": {
                "factor_name": "earnings_quality_composite",
                "universe_name": "large_cap_research_slice_demo_v0",
                "horizon_type": "next_month",
                "return_basis": "raw",
            },
            "requested_by": "operator",
            "cited_evidence_packet_ids": ["ValidationPromotionEvaluationV1:ev_demo_1"],
            "queued_at_utc": "2026-04-20T10:00:00+00:00",
        },
    }
    base.update(over)
    return base


def _res_kwargs(**over) -> dict:
    base = {
        "packet_id": deterministic_packet_id(
            packet_type="SandboxResultPacketV1",
            created_by_agent="layer3.sandbox_executor_v1",
            target_scope={"registry_entry_id": "reg_short_demo_v0"},
        ),
        "packet_type": "SandboxResultPacketV1",
        "target_layer": "layer3_research",
        "created_by_agent": "layer3.sandbox_executor_v1",
        "target_scope": {"registry_entry_id": "reg_short_demo_v0"},
        "provenance_refs": ["SandboxRequestPacketV1:sbx_req_demo_1"],
        "confidence": 0.8,
        "blocking_reasons": [],
        "payload": {
            "result_id": "sbx_res_demo_1",
            "cited_request_packet_id": "SandboxRequestPacketV1:sbx_req_demo_1",
            "outcome": "completed",
            "produced_refs": ["factor_validation_run:fvr_sbx_done_1"],
            "blocking_reasons": [],
            "completed_at_utc": "2026-04-20T10:05:00+00:00",
        },
    }
    base.update(over)
    return base


def test_sandbox_enums_are_minimal_for_patch5():
    # Patch 5 closed-loop surface: validation_rerun only.
    assert SANDBOX_KINDS == ("validation_rerun",)
    assert "operator" in SANDBOX_REQUEST_ACTORS
    assert "research_ask_v1" in SANDBOX_REQUEST_ACTORS
    for required in (
        "completed",
        "blocked_insufficient_inputs",
        "rejected_kind_not_allowed",
        "errored",
    ):
        assert required in SANDBOX_RESULT_OUTCOMES


def test_sandbox_packet_types_registered():
    for t in ("SandboxRequestPacketV1", "SandboxResultPacketV1"):
        assert t in PACKET_TYPES
        assert t in PACKET_TYPE_TO_CLASS


def test_sandbox_queue_class_registered_once():
    assert "sandbox_queue" in QUEUE_CLASSES
    assert QUEUE_CLASSES.count("sandbox_queue") == 1


def test_sandbox_request_rejects_unknown_sandbox_kind():
    kwargs = _req_kwargs()
    kwargs["payload"] = {**kwargs["payload"], "sandbox_kind": "evidence_refresh"}
    with pytest.raises(ValidationError):
        SandboxRequestPacketV1.model_validate(kwargs)


def test_sandbox_request_requires_target_spec_fields_for_validation_rerun():
    kwargs = _req_kwargs()
    kwargs["payload"] = {
        **kwargs["payload"],
        "target_spec": {
            "factor_name": "earnings_quality_composite",
            "universe_name": "",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
    }
    with pytest.raises(ValidationError):
        SandboxRequestPacketV1.model_validate(kwargs)


def test_sandbox_request_happy_path_is_valid():
    req = SandboxRequestPacketV1.model_validate(_req_kwargs())
    assert req.payload["sandbox_kind"] == "validation_rerun"


def test_sandbox_result_rejects_invalid_outcome():
    kwargs = _res_kwargs()
    kwargs["payload"] = {**kwargs["payload"], "outcome": "green_lit"}
    with pytest.raises(ValidationError):
        SandboxResultPacketV1.model_validate(kwargs)


def test_sandbox_result_blocked_requires_blocking_reasons():
    kwargs = _res_kwargs()
    kwargs["payload"] = {
        **kwargs["payload"],
        "outcome": "blocked_insufficient_inputs",
        "produced_refs": [],
        "blocking_reasons": [],
    }
    with pytest.raises(ValidationError):
        SandboxResultPacketV1.model_validate(kwargs)


def test_sandbox_result_completed_happy_path_is_valid():
    res = SandboxResultPacketV1.model_validate(_res_kwargs())
    assert res.payload["outcome"] == "completed"


def test_sandbox_migration_whitelists_new_types():
    repo = Path(__file__).resolve().parents[2]
    mig = repo / "supabase" / "migrations" / "20260420100000_agh_v1_patch_5_research_sandbox.sql"
    assert mig.is_file(), "Patch 5 sandbox migration must exist"
    text = mig.read_text(encoding="utf-8")
    # Packet CK whitelist.
    assert "'SandboxRequestPacketV1'" in text
    assert "'SandboxResultPacketV1'" in text
    # Queue CK whitelist.
    assert "'sandbox_queue'" in text
    # Constraint names must match the drop/add pattern.
    assert "agentic_harness_packets_v1_packet_type_ck" in text
    assert "agentic_harness_queue_jobs_v1_queue_class_ck" in text
