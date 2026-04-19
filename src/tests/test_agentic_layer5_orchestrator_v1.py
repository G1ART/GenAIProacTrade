"""Layer 5 (bounded LLM orchestrator) tests (AGH-8).

All tests use ``FixtureProvider`` directly so nothing can reach the
network even if OPENAI_API_KEY happens to be set in the environment.
"""

from __future__ import annotations

import pytest

from agentic_harness.agents.layer1_ingest import (
    ingest_coordinator_agent,
    event_trigger_agent,
)
from agentic_harness.agents.layer5_orchestrator import (
    _SYSTEM_PROMPT,
    action_router_agent,
    founder_user_orchestrator_agent,
    run_layer5_ask,
    state_reader_agent,
)
from agentic_harness.contracts.packets_v1 import (
    OverlayProposalPacketV1,
    ResearchCandidatePacketV1,
    deterministic_packet_id,
)
from agentic_harness.llm.contract import LLMResponseContractV1
from agentic_harness.llm.provider import FixtureProvider
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


def _store_with_one_asset_packet() -> tuple[FixtureHarnessStore, str]:
    store = FixtureHarnessStore()
    trigger = event_trigger_agent(
        candidate={
            "asset_id": "TRGP",
            "last_fetched_at_utc": "",
            "expected_freshness_hours": 72,
        },
        now_iso=now_utc_iso(),
    )
    res = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now_utc_iso())
    assert res is not None
    return store, res["alert_packet_id"]


@pytest.mark.parametrize(
    "question, expected_kind",
    [
        ("오늘 왜 이 종목 주가가 움직였지?", "why_changed"),
        ("Why did this name change today?", "why_changed"),
        ("지금 시스템 큐 상태가 어때?", "system_status"),
        ("Show system status of queues.", "system_status"),
        ("대기중인 연구 후보 있어?", "research_pending"),
        ("Research pending on this asset?", "research_pending"),
        ("random gibberish that matches nothing", "why_changed"),
    ],
)
def test_action_router_classifies_three_kinds(question, expected_kind):
    assert action_router_agent(question) == expected_kind


def test_state_reader_scopes_by_asset_id():
    store, _pid = _store_with_one_asset_packet()
    bundle = state_reader_agent(
        store=store, asset_id="TRGP", routed_kind="why_changed"
    )
    assert bundle["asset_id"] == "TRGP"
    assert bundle["contract"] == "METIS_AGENTIC_HARNESS_STATE_BUNDLE_V1"


def test_orchestrator_happy_path_uses_fixture_provider_and_writes_packet():
    store, _ = _store_with_one_asset_packet()
    out = founder_user_orchestrator_agent(
        store=store,
        question="왜 오늘 움직였지?",
        asset_id="TRGP",
        provider=FixtureProvider(),
    )
    assert out["routed_kind"] == "why_changed"
    assert out["guardrail_passed"] is True
    assert out["response"]["llm_fallback"] is False
    saved = store.get_packet(out["user_query_action_packet_id"])
    assert saved["packet_type"] == "UserQueryActionPacketV1"


def test_orchestrator_forbidden_token_triggers_fallback():
    store, _ = _store_with_one_asset_packet()
    bad_provider = FixtureProvider(
        override_response={
            "answer_ko": "오늘 이 종목은 무조건 오른다고 확신.",
            "answer_en": "You should definitely buy this name now.",
            "cited_packet_ids": ["bundle:why_changed:TRGP"],
            "fact_vs_interpretation_map": {},
            "recheck_rule": "now",
            "blocking_reasons": [],
        }
    )
    out = founder_user_orchestrator_agent(
        store=store,
        question="why changed today?",
        asset_id="TRGP",
        provider=bad_provider,
    )
    assert out["guardrail_passed"] is False
    assert out["response"]["llm_fallback"] is True
    assert out["response"]["fallback_reason"].startswith("forbidden_copy:")


def test_orchestrator_rejects_hallucinated_cited_ids():
    store, allowed_id = _store_with_one_asset_packet()
    halluc = FixtureProvider(
        override_response={
            "answer_ko": "기술적 변동이 있었습니다.",
            "answer_en": "Technical move observed.",
            "cited_packet_ids": ["pkt_totally_made_up"],
            "fact_vs_interpretation_map": {"pkt_totally_made_up": "interpretation"},
            "recheck_rule": "recheck_next_harness_tick",
            "blocking_reasons": [],
        }
    )
    out = founder_user_orchestrator_agent(
        store=store,
        question="why changed today?",
        asset_id="TRGP",
        provider=halluc,
    )
    assert out["guardrail_passed"] is False
    assert out["response"]["fallback_reason"].startswith("hallucinated_cited_ids:")


def test_orchestrator_schema_violation_triggers_fallback():
    store, _ = _store_with_one_asset_packet()
    empty_cited = FixtureProvider(
        override_response={
            "answer_ko": "상태를 요약합니다.",
            "answer_en": "Summary of state.",
            "cited_packet_ids": [],  # contract requires >=1
            "fact_vs_interpretation_map": {},
            "recheck_rule": "recheck_next_harness_tick",
            "blocking_reasons": [],
        }
    )
    out = founder_user_orchestrator_agent(
        store=store,
        question="system status?",
        asset_id="TRGP",
        provider=empty_cited,
    )
    assert out["guardrail_passed"] is False
    assert out["response"]["fallback_reason"].startswith("schema_violation")


def test_run_layer5_ask_with_fixture_default_is_network_free(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("METIS_HARNESS_LLM_PROVIDER", raising=False)
    store, _ = _store_with_one_asset_packet()
    out = run_layer5_ask(
        store=store,
        asset_id="TRGP",
        question="왜 움직였지?",
    )
    assert out["provider_name"] == "fixture"


def _insert_asset_neutral_overlay(store: FixtureHarnessStore) -> str:
    pid = deterministic_packet_id(
        packet_type="OverlayProposalPacketV1",
        created_by_agent="research_engine_agent",
        target_scope={"source_family": "earnings_transcript"},
        salt="neutral-overlay-1",
    )
    pkt = OverlayProposalPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "OverlayProposalPacketV1",
            "target_layer": "layer3_research",
            "created_by_agent": "research_engine_agent",
            "target_scope": {"source_family": "earnings_transcript"},
            "provenance_refs": ["seed://overlay_neutral"],
            "confidence": 0.55,
            "payload": {
                "overlay_type": "regime_shift",
                "expected_direction_hint": "regime_changes",
                "why_it_matters": "universe-wide tone shift observed across calls",
            },
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pid


def _insert_asset_neutral_research_candidate(store: FixtureHarnessStore) -> str:
    persona = {
        "candidate_id": "pcand_universe_v1",
        "persona": "quant_residual_analyst",
        "thesis_family": "residual_tightening_shortlist",
        "targeted_horizon": "short",
        "targeted_universe": "combined_largecap_research_v1",
        "evidence_refs": [{"kind": "seed", "pointer": "seed://x", "summary": "ok"}],
        "confidence": 0.62,
        "signal_type": "residual_tightening",
        "intended_overlay_type": "confidence_adjustment",
        "blocking_reasons": ["requires_pit_rule_certification"],
    }
    pid = deterministic_packet_id(
        packet_type="ResearchCandidatePacketV1",
        created_by_agent="research_engine_agent",
        target_scope={"universe": "combined_largecap_research_v1"},
        salt="neutral-research-1",
    )
    pkt = ResearchCandidatePacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "ResearchCandidatePacketV1",
            "target_layer": "layer3_research",
            "created_by_agent": "research_engine_agent",
            "target_scope": {"universe": "combined_largecap_research_v1"},
            "provenance_refs": ["seed://persona_universe"],
            "confidence": 0.6,
            "payload": {
                "persona_candidate_packet": persona,
                "signal_type": "residual_tightening",
                "intended_overlay_type": "confidence_adjustment",
            },
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pid


def test_state_reader_research_pending_includes_asset_neutral_candidates():
    store, _ = _store_with_one_asset_packet()
    neutral_id = _insert_asset_neutral_research_candidate(store)
    bundle = state_reader_agent(
        store=store, asset_id="TRGP", routed_kind="research_pending"
    )
    ids = {str(p.get("packet_id")) for p in bundle["relevant_packets"]}
    assert neutral_id in ids, (
        "asset-neutral ResearchCandidatePacketV1 must surface under research_pending "
        "even when the user pins a specific asset"
    )


def test_state_reader_why_changed_includes_neutral_overlay_but_not_neutral_research():
    store, alert_id = _store_with_one_asset_packet()
    overlay_neutral_id = _insert_asset_neutral_overlay(store)
    research_neutral_id = _insert_asset_neutral_research_candidate(store)
    bundle = state_reader_agent(
        store=store, asset_id="TRGP", routed_kind="why_changed"
    )
    ids = {str(p.get("packet_id")) for p in bundle["relevant_packets"]}
    assert alert_id in ids, "asset-scoped IngestAlert must be in why_changed bundle"
    assert overlay_neutral_id in ids, (
        "asset-neutral OverlayProposal must be included in why_changed bundle as a signal"
    )
    assert research_neutral_id not in ids, (
        "ResearchCandidate is not a why_changed packet type; must NOT leak into that bundle"
    )


def test_system_prompt_forbids_today_active_state_claims():
    for phrase in (
        "NEVER claim that the Today registry has changed",
        "signals to watch",
        "promotion gate",
    ):
        assert phrase in _SYSTEM_PROMPT, (
            f"system prompt missing surface-guard phrase: {phrase!r}"
        )


def test_system_prompt_teaches_artifact_promotion_vocabulary():
    """Patch 3 vocabulary must be present so the LLM can describe an
    active/challenger swap and cite the spectrum-refresh audit packet."""

    for phrase in (
        "registry_entry_artifact_promotion",
        "SpectrumRefreshRecordV1",
        "needs_db_rebuild",
    ):
        assert phrase in _SYSTEM_PROMPT, (
            f"system prompt missing Patch 3 vocabulary: {phrase!r}"
        )


def _insert_spectrum_refresh_record(
    store: FixtureHarnessStore, *, horizon: str = "short"
) -> str:
    pid = deterministic_packet_id(
        packet_type="SpectrumRefreshRecordV1",
        created_by_agent="registry_patch_executor",
        target_scope={"applied_packet_id": "pkt_applied_demo_v0"},
        salt=f"refresh-{horizon}",
    )
    row = {
        "packet_id": pid,
        "packet_type": "SpectrumRefreshRecordV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "registry_patch_executor",
        "created_at_utc": now_utc_iso(),
        "target_scope": {"applied_packet_id": "pkt_applied_demo_v0"},
        "provenance_refs": ["packet:pkt_applied_demo_v0"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "horizon": horizon,
            "registry_entry_id": f"reg_{horizon}_demo_v0",
            "outcome": "carry_over_fixture_fallback",
            "refresh_mode": "fixture_fallback",
            "needs_db_rebuild": True,
            "cited_applied_packet_id": "pkt_applied_demo_v0",
            "cited_proposal_packet_id": "pkt_proposal_demo_v0",
            "cited_decision_packet_id": "pkt_decision_demo_v0",
            "refreshed_at_utc": now_utc_iso(),
            "bundle_path": "/tmp/bundle.json",
            "before_row_count": 3,
            "after_row_count": 3,
            "before_row_asset_ids_sample": ["A", "B", "C"],
            "after_row_asset_ids_sample": ["A", "B", "C"],
            "blocking_reasons": ["supabase_client_missing_or_fixture_mode"],
        },
    }
    store.upsert_packet(row)
    return pid


def test_state_reader_why_changed_includes_spectrum_refresh_record():
    """SpectrumRefreshRecordV1 is asset-neutral but must reach the why_changed
    bundle so the LLM can mention that a governed apply just refreshed the
    horizon and whether the new rows are carried-over (DB rebuild pending)."""

    store, _ = _store_with_one_asset_packet()
    refresh_id = _insert_spectrum_refresh_record(store, horizon="short")
    bundle = state_reader_agent(
        store=store, asset_id="TRGP", routed_kind="why_changed"
    )
    ids = {str(p.get("packet_id")) for p in bundle["relevant_packets"]}
    assert refresh_id in ids, (
        "SpectrumRefreshRecordV1 must be surfaced in why_changed bundle as a "
        "governance-lineage signal, regardless of asset scope"
    )


def test_contract_rejects_fact_map_with_unknown_key():
    with pytest.raises(Exception):
        LLMResponseContractV1.model_validate(
            {
                "answer_ko": "ok",
                "answer_en": "ok",
                "cited_packet_ids": ["pkt_a"],
                "fact_vs_interpretation_map": {"pkt_b": "fact"},
                "recheck_rule": "",
                "blocking_reasons": [],
            }
        )
