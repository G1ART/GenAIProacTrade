"""AGH v1 Patch 6 — D1 locale_coverage contract + guardrail + system prompt.

``ResearchAnswerStructureV1`` now forbids the silent Patch-5 degrade where
one locale was empty while the other was populated. Callers must declare
``locale_coverage`` honestly; both the Pydantic model-validator and the
``validate_research_structured_v1`` guardrail block mismatched claims.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_harness.llm.contract import (
    LOCALE_COVERAGE_KINDS,
    ResearchAnswerStructureV1,
)
from agentic_harness.llm.guardrails import validate_research_structured_v1


def _structure_kwargs(**overrides):
    base = {
        "summary_bullets_ko": ["요약 한 줄"],
        "summary_bullets_en": ["summary line"],
        "rationale": "",
        "residual_uncertainty_bullets": [],
        "what_to_watch_bullets": [],
        "evidence_cited": [],
        "cited_packet_ids": [],
        "proposed_sandbox_request": None,
        "locale_coverage": "dual",
    }
    base.update(overrides)
    return base


def test_locale_coverage_constant_lists_all_four_kinds() -> None:
    assert set(LOCALE_COVERAGE_KINDS) == {"dual", "ko_only", "en_only", "degraded"}


def test_locale_coverage_dual_accepts_both_bullets_populated() -> None:
    rs = ResearchAnswerStructureV1(**_structure_kwargs())
    assert rs.locale_coverage == "dual"
    assert rs.summary_bullets_ko and rs.summary_bullets_en


def test_locale_coverage_dual_rejects_en_only_silent_degrade() -> None:
    with pytest.raises(ValidationError) as exc:
        ResearchAnswerStructureV1(
            **_structure_kwargs(
                summary_bullets_ko=[],
                summary_bullets_en=["summary"],
                locale_coverage="dual",
            )
        )
    assert "locale_claim_mismatch" in str(exc.value)


def test_locale_coverage_dual_rejects_ko_only_silent_degrade() -> None:
    with pytest.raises(ValidationError) as exc:
        ResearchAnswerStructureV1(
            **_structure_kwargs(
                summary_bullets_ko=["요약"],
                summary_bullets_en=[],
                locale_coverage="dual",
            )
        )
    assert "locale_claim_mismatch" in str(exc.value)


def test_locale_coverage_ko_only_requires_en_empty() -> None:
    rs = ResearchAnswerStructureV1(
        **_structure_kwargs(
            summary_bullets_ko=["요약"],
            summary_bullets_en=[],
            locale_coverage="ko_only",
        )
    )
    assert rs.locale_coverage == "ko_only"

    with pytest.raises(ValidationError) as exc:
        ResearchAnswerStructureV1(
            **_structure_kwargs(
                summary_bullets_ko=["요약"],
                summary_bullets_en=["summary"],
                locale_coverage="ko_only",
            )
        )
    assert "locale_claim_mismatch" in str(exc.value)


def test_locale_coverage_en_only_requires_ko_empty() -> None:
    rs = ResearchAnswerStructureV1(
        **_structure_kwargs(
            summary_bullets_ko=[],
            summary_bullets_en=["summary"],
            locale_coverage="en_only",
        )
    )
    assert rs.locale_coverage == "en_only"

    with pytest.raises(ValidationError):
        ResearchAnswerStructureV1(
            **_structure_kwargs(
                summary_bullets_ko=["요약"],
                summary_bullets_en=["summary"],
                locale_coverage="en_only",
            )
        )


def test_locale_coverage_degraded_requires_both_bullets_empty() -> None:
    rs = ResearchAnswerStructureV1(
        **_structure_kwargs(
            summary_bullets_ko=[],
            summary_bullets_en=[],
            locale_coverage="degraded",
            rationale="Evidence too thin for any summary.",
        )
    )
    assert rs.locale_coverage == "degraded"
    assert rs.summary_bullets_ko == []
    assert rs.summary_bullets_en == []

    with pytest.raises(ValidationError):
        ResearchAnswerStructureV1(
            **_structure_kwargs(
                summary_bullets_ko=["요약"],
                summary_bullets_en=[],
                locale_coverage="degraded",
            )
        )


def test_guardrail_blocks_dual_claim_with_one_empty_locale() -> None:
    # Bypass Pydantic and feed the raw dict directly to the guardrail. This is
    # the shape ``layer5_orchestrator`` passes in before constructing the
    # Pydantic model — we must still catch the claim mismatch.
    blocking = validate_research_structured_v1(
        research_structured={
            "summary_bullets_ko": ["요약"],
            "summary_bullets_en": [],
            "residual_uncertainty_bullets": [],
            "what_to_watch_bullets": [],
            "evidence_cited": [],
            "locale_coverage": "dual",
        },
        routed_kind="deeper_rationale",
        allowed_packet_ids=[],
    )
    assert any("locale_claim_mismatch" in r for r in blocking), blocking


def test_guardrail_accepts_ko_only_when_en_empty() -> None:
    blocking = validate_research_structured_v1(
        research_structured={
            "summary_bullets_ko": ["요약"],
            "summary_bullets_en": [],
            "residual_uncertainty_bullets": [],
            "what_to_watch_bullets": [],
            "evidence_cited": [],
            "locale_coverage": "ko_only",
        },
        routed_kind="deeper_rationale",
        allowed_packet_ids=[],
    )
    assert not any("locale_claim_mismatch" in r for r in blocking), blocking


def test_system_prompt_mentions_locale_coverage_honesty() -> None:
    # The orchestrator prompt must tell the LLM how to set locale_coverage.
    from agentic_harness.agents.layer5_orchestrator import _SYSTEM_PROMPT

    assert "locale_coverage" in _SYSTEM_PROMPT
    assert "dual" in _SYSTEM_PROMPT
    assert "ko_only" in _SYSTEM_PROMPT
    assert "en_only" in _SYSTEM_PROMPT
    assert "degraded" in _SYSTEM_PROMPT
