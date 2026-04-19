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
    action_router_agent,
    founder_user_orchestrator_agent,
    run_layer5_ask,
    state_reader_agent,
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
