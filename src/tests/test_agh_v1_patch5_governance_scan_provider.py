"""AGH v1 Patch 5 — governance_scan Supabase provider tests.

Guards the production ``governance_scan`` spec provider so it:

    1. Joins ``factor_validation_runs`` + ``factor_validation_summaries``
       to the brain bundle on ``universe`` + ``horizon`` and each
       registry entry's ``research_factor_bindings_v1``.
    2. Honest-skips registry entries that declare no factor bindings
       (Patch 5 §A2: no free-form inference of bindings).
    3. Is idempotent across ticks — a second call against the same
       evidence + a packet-store that already holds the matching
       ``ValidationPromotionEvaluationV1`` returns an empty spec list.
    4. Uses the deterministic ``derive_artifact_id`` policy to match
       existing evaluations, so "same evidence -> same artifact id" is
       preserved even when the stored packet was written by Patch 4.

These tests never need a real Supabase connection: they inject a tiny
stub client that mimics the ``.table(...).select(...).eq(...).execute()``
fluent surface the provider expects.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentic_harness.agents.governance_scan_provider_v1 import (
    deduplicate_specs,
    list_recent_completed_validation_runs,
    match_runs_to_registry_entries,
    scan_and_build_specs,
)
from agentic_harness.agents.layer4_promotion_evaluator_v1 import derive_artifact_id
from agentic_harness.contracts.packets_v1 import deterministic_packet_id
from agentic_harness.store import FixtureHarnessStore


# ---------------------------------------------------------------------------
# Stub Supabase client (only what the provider touches).
# ---------------------------------------------------------------------------


class _StubQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def gte(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def in_(self, *_a, **_kw):
        return self

    def execute(self):
        return SimpleNamespace(data=list(self._rows))


class _StubClient:
    def __init__(self, *, runs: list[dict], summaries: list[dict]):
        self._runs = runs
        self._summaries = summaries

    def table(self, name: str):
        if name == "factor_validation_runs":
            return _StubQuery(self._runs)
        if name == "factor_validation_summaries":
            return _StubQuery(self._summaries)
        return _StubQuery([])


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


RUN_ID = "run_demo_completed_1"

_RUNS = [
    {
        "id": RUN_ID,
        "universe_name": "large_cap_research_slice_demo_v0",
        "horizon_type": "next_month",
        "completed_at": "2026-04-18T00:00:00+00:00",
        "status": "completed",
    }
]
_SUMMARIES = [
    {
        "run_id": RUN_ID,
        "factor_name": "earnings_quality_composite",
        "return_basis": "raw",
    },
]


def _bundle_with_binding(**override_entry) -> dict:
    ent = {
        "registry_entry_id": "reg_short_demo_v0",
        "horizon": "short",
        "status": "active_demo",
        "active_model_family_name": "factor_demo",
        "active_artifact_id": "artifact_demo",
        "challenger_artifact_ids": [],
        "universe": "large_cap_research_slice_demo_v0",
        "scoring_endpoint_contract": "seed_inline_v0",
        "research_factor_bindings_v1": [
            {"factor_name": "earnings_quality_composite", "return_basis": "raw"}
        ],
    }
    ent.update(override_entry)
    return {"registry_entries": [ent]}


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_list_recent_completed_validation_runs_expands_summaries():
    client = _StubClient(runs=_RUNS, summaries=_SUMMARIES)
    out = list_recent_completed_validation_runs(
        client, since_iso="2026-04-01T00:00:00+00:00"
    )
    assert len(out) == 1
    assert out[0]["run_id"] == RUN_ID
    assert out[0]["factor_name"] == "earnings_quality_composite"
    assert out[0]["return_basis"] == "raw"


def test_match_runs_to_registry_entries_emits_spec_with_evidence():
    runs = [
        {
            "run_id": RUN_ID,
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "completed_at": "2026-04-18T00:00:00+00:00",
            "factor_name": "earnings_quality_composite",
            "return_basis": "raw",
        }
    ]
    specs = match_runs_to_registry_entries(runs, _bundle_with_binding())
    assert len(specs) == 1
    s = specs[0]
    assert s["registry_entry_id"] == "reg_short_demo_v0"
    assert s["horizon"] == "short"
    assert s["_evidence"]["validation_run_id"] == RUN_ID


def test_match_honest_skips_entries_without_research_factor_bindings_v1():
    bundle = _bundle_with_binding()
    bundle["registry_entries"][0]["research_factor_bindings_v1"] = []
    runs = [
        {
            "run_id": RUN_ID,
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "completed_at": "2026-04-18T00:00:00+00:00",
            "factor_name": "earnings_quality_composite",
            "return_basis": "raw",
        }
    ]
    specs = match_runs_to_registry_entries(runs, bundle)
    assert specs == []


def test_deduplicate_specs_drops_spec_already_evaluated():
    store = FixtureHarnessStore()
    specs = match_runs_to_registry_entries(
        [
            {
                "run_id": RUN_ID,
                "universe_name": "large_cap_research_slice_demo_v0",
                "horizon_type": "next_month",
                "completed_at": "2026-04-18T00:00:00+00:00",
                "factor_name": "earnings_quality_composite",
                "return_basis": "raw",
            }
        ],
        _bundle_with_binding(),
    )
    assert len(specs) == 1
    spec = specs[0]
    derived = derive_artifact_id(
        factor_name=spec["factor_name"],
        universe_name=spec["universe_name"],
        horizon_type=spec["horizon_type"],
        return_basis=spec["return_basis"],
        validation_run_id=spec["_evidence"]["validation_run_id"],
    )
    # Seed a pre-existing matching ValidationPromotionEvaluationV1.
    store.upsert_packet(
        {
            "packet_id": deterministic_packet_id(
                packet_type="ValidationPromotionEvaluationV1",
                created_by_agent="layer4.promotion_evaluator_v1",
                target_scope={"registry_entry_id": spec["registry_entry_id"]},
            ),
            "packet_type": "ValidationPromotionEvaluationV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "layer4.promotion_evaluator_v1",
            "target_scope": {"registry_entry_id": spec["registry_entry_id"]},
            "provenance_refs": [
                f"factor_validation_run:{spec['_evidence']['validation_run_id']}"
            ],
            "confidence": 0.8,
            "blocking_reasons": [],
            "payload": {
                "registry_entry_id": spec["registry_entry_id"],
                "horizon": spec["horizon"],
                "derived_artifact_id": derived,
                "validation_run_id": spec["_evidence"]["validation_run_id"],
                "outcome": "proposal_emitted",
                "verdict": "promote",
                "validation_pointer": (
                    f"factor_validation_run:{spec['_evidence']['validation_run_id']}:"
                    f"{spec['factor_name']}:{spec['return_basis']}"
                ),
                "factor_name": spec["factor_name"],
                "universe_name": spec["universe_name"],
                "horizon_type": spec["horizon_type"],
                "return_basis": spec["return_basis"],
                "emitted_proposal_packet_id": "RegistryUpdateProposalV1:demo",
            },
        }
    )
    assert deduplicate_specs(store, specs) == []


def test_scan_and_build_specs_idempotent_end_to_end():
    store = FixtureHarnessStore()
    client = _StubClient(runs=_RUNS, summaries=_SUMMARIES)
    bundle = _bundle_with_binding()
    # First pass: bundle contains a binding, no prior evaluation -> 1 spec.
    first = scan_and_build_specs(
        store,
        client=client,
        bundle_dict=bundle,
        now_iso="2026-04-19T00:00:00+00:00",
    )
    assert len(first) == 1
    # Seed matching evaluation -> second pass returns nothing.
    spec = first[0]
    derived = derive_artifact_id(
        factor_name=spec["factor_name"],
        universe_name=spec["universe_name"],
        horizon_type=spec["horizon_type"],
        return_basis=spec["return_basis"],
        validation_run_id=spec["_evidence"]["validation_run_id"],
    )
    store.upsert_packet(
        {
            "packet_id": "ValidationPromotionEvaluationV1:idem_1",
            "packet_type": "ValidationPromotionEvaluationV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "layer4.promotion_evaluator_v1",
            "target_scope": {"registry_entry_id": spec["registry_entry_id"]},
            "provenance_refs": [
                f"factor_validation_run:{spec['_evidence']['validation_run_id']}"
            ],
            "confidence": 0.8,
            "blocking_reasons": [],
            "payload": {
                "registry_entry_id": spec["registry_entry_id"],
                "horizon": spec["horizon"],
                "derived_artifact_id": derived,
                "validation_run_id": spec["_evidence"]["validation_run_id"],
                "outcome": "proposal_emitted",
                "verdict": "promote",
                "validation_pointer": (
                    f"factor_validation_run:{spec['_evidence']['validation_run_id']}:"
                    f"{spec['factor_name']}:{spec['return_basis']}"
                ),
                "factor_name": spec["factor_name"],
                "universe_name": spec["universe_name"],
                "horizon_type": spec["horizon_type"],
                "return_basis": spec["return_basis"],
                "emitted_proposal_packet_id": "RegistryUpdateProposalV1:idem_1",
            },
        }
    )
    second = scan_and_build_specs(
        store,
        client=client,
        bundle_dict=bundle,
        now_iso="2026-04-19T01:00:00+00:00",
    )
    assert second == []
