"""AGH v1 Patch 5 — ResearchAnswerStructureV1 + validate_research_structured_v1 tests.

Covers the Research Ask acceptance contract (Patch 5 §B2/B3):

    * Structured block required on research kinds, absent block ok on
      ``why_changed`` / ``system_status`` / ``research_pending``.
    * ``evidence_cited`` must be a subset of ``allowed_packet_ids``
      (hallucinated ids block the answer).
    * Forbidden-copy guardrail catches buy/sell/gambling copy smuggled
      into any bullet or the proposed sandbox rationale.
    * ``proposed_sandbox_request.sandbox_kind`` is narrowed to the
       Patch 5 enum (``validation_rerun`` only).
    * ``LLMResponseContractV1`` cross-model validator enforces
      ``research_structured_v1.evidence_cited ⊆ cited_packet_ids``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_harness.llm.contract import (
    LLMResponseContractV1,
    RESEARCH_STRUCTURED_KINDS,
    ResearchAnswerStructureV1,
)
from agentic_harness.llm.guardrails import validate_research_structured_v1


def _good_structured(**over) -> dict:
    base = {
        "summary_bullets_ko": ["현재 해석은 증거 A에 근거한다"],
        "summary_bullets_en": ["Current interpretation rests on Evidence A"],
        "residual_uncertainty_bullets": [
            "아직 증명되지 않은 구간: 분기별 하락장 커버리지"
        ],
        "what_to_watch_bullets": ["다음 분기 factor_quantile_results 재검증"],
        "evidence_cited": ["ValidationPromotionEvaluationV1:ev_demo_1"],
        "proposed_sandbox_request": None,
    }
    base.update(over)
    return base


def _good_response(**over) -> dict:
    base = {
        "answer_ko": "증거 A 기반 현재 해석",
        "answer_en": "Current interpretation rests on Evidence A",
        "rationale": "As documented in the cited packets.",
        "cited_packet_ids": ["ValidationPromotionEvaluationV1:ev_demo_1"],
        "fact_vs_interpretation_map": {
            "ValidationPromotionEvaluationV1:ev_demo_1": "fact",
        },
        "blocking_reasons": [],
        "guardrail_violations_count": 0,
        "fallback_reason": "",
        "research_structured_v1": _good_structured(),
    }
    base.update(over)
    return base


def test_research_structured_required_on_research_kinds():
    for k in RESEARCH_STRUCTURED_KINDS:
        blocking = validate_research_structured_v1(
            research_structured=None,
            routed_kind=k,
            allowed_packet_ids=["ValidationPromotionEvaluationV1:ev_demo_1"],
        )
        assert blocking, f"{k} must require structured block"
        assert any("missing_research_structured" in b for b in blocking)


def test_research_structured_optional_on_non_research_kinds():
    for k in ("why_changed", "system_status", "research_pending"):
        blocking = validate_research_structured_v1(
            research_structured=None,
            routed_kind=k,
            allowed_packet_ids=["ValidationPromotionEvaluationV1:ev_demo_1"],
        )
        assert blocking == []


def test_research_structured_evidence_cited_subset_rule():
    blocking = validate_research_structured_v1(
        research_structured=_good_structured(
            evidence_cited=["HallucinatedPacket:abc", "HallucinatedPacket:def"]
        ),
        routed_kind="deeper_rationale",
        allowed_packet_ids=["ValidationPromotionEvaluationV1:ev_demo_1"],
    )
    assert any("evidence_cited_hallucinated" in b for b in blocking)


def test_research_structured_forbidden_copy_in_bullet():
    # ``확실`` and the English ``recommend``/``buy`` family are guardrail
    # tokens. Using ``buy`` lets us verify that forbidden-copy scanning
    # actually runs on each bullet list.
    blocking = validate_research_structured_v1(
        research_structured=_good_structured(
            summary_bullets_en=["buy this now"],
        ),
        routed_kind="deeper_rationale",
        allowed_packet_ids=["ValidationPromotionEvaluationV1:ev_demo_1"],
    )
    assert any("forbidden_copy" in b for b in blocking)


def test_research_structured_clean_block_passes():
    blocking = validate_research_structured_v1(
        research_structured=_good_structured(),
        routed_kind="deeper_rationale",
        allowed_packet_ids=["ValidationPromotionEvaluationV1:ev_demo_1"],
    )
    assert blocking == []


def test_research_answer_structure_rejects_unknown_sandbox_kind():
    with pytest.raises(ValidationError):
        ResearchAnswerStructureV1.model_validate(
            _good_structured(
                proposed_sandbox_request={
                    "sandbox_kind": "evidence_refresh",
                    "registry_entry_id": "reg_short_demo_v0",
                    "horizon": "short",
                    "target_spec": {
                        "factor_name": "earnings_quality_composite",
                        "universe_name": "large_cap_research_slice_demo_v0",
                        "horizon_type": "next_month",
                        "return_basis": "raw",
                    },
                    "rationale": "because",
                }
            )
        )


def test_llm_response_cross_model_validator_enforces_subset_of_cited():
    # Structured block cites an id that is NOT in the top-level
    # cited_packet_ids -> the contract itself must reject the response.
    bad = _good_response()
    bad["research_structured_v1"] = _good_structured(
        evidence_cited=["SomeOtherPacket:zzz"]
    )
    with pytest.raises(ValidationError):
        LLMResponseContractV1.model_validate(bad)


def test_llm_response_contract_happy_path_is_valid():
    resp = LLMResponseContractV1.model_validate(_good_response())
    assert resp.research_structured_v1 is not None
    assert resp.research_structured_v1.evidence_cited == [
        "ValidationPromotionEvaluationV1:ev_demo_1"
    ]
