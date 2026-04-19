"""``LLMResponseContractV1`` - the only shape Layer 5 surfaces back to users.

Free-form LLM text is rejected at two levels:

  1. JSON schema enforcement (this module).
  2. Forbidden-copy guardrails (``guardrails.py``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FactVsInterpretation = Literal["fact", "interpretation"]
USER_QUESTION_KINDS = ("why_changed", "system_status", "research_pending")


class LLMResponseContractV1(BaseModel):
    contract: str = "METIS_AGENTIC_HARNESS_LLM_RESPONSE_V1"

    answer_ko: str = Field(max_length=600)
    answer_en: str = Field(max_length=600)
    cited_packet_ids: list[str] = Field(default_factory=list)
    fact_vs_interpretation_map: dict[str, FactVsInterpretation] = Field(default_factory=dict)
    recheck_rule: str = Field(default="")
    blocking_reasons: list[str] = Field(default_factory=list)

    # Operational flags the orchestrator sets after the LLM returns - they
    # are part of the contract so audit consumers can see them.
    llm_fallback: bool = False
    fallback_reason: str = ""

    @field_validator("cited_packet_ids")
    @classmethod
    def _cited_at_least_one(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("cited_packet_ids must be a list")
        out = [str(x).strip() for x in v if str(x or "").strip()]
        if not out:
            raise ValueError("cited_packet_ids must contain at least one ref")
        return out

    @field_validator("answer_ko", "answer_en")
    @classmethod
    def _non_empty_answers(cls, v: str) -> str:
        v = str(v or "").strip()
        if not v:
            raise ValueError("answer fields must be non-empty")
        return v

    @model_validator(mode="after")
    def _fact_map_keys_subset_of_cited(self) -> "LLMResponseContractV1":
        cited = set(self.cited_packet_ids)
        for k in self.fact_vs_interpretation_map.keys():
            if k not in cited:
                raise ValueError(
                    f"fact_vs_interpretation_map key {k!r} is not in cited_packet_ids"
                )
        return self


RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer_ko",
        "answer_en",
        "cited_packet_ids",
        "fact_vs_interpretation_map",
        "recheck_rule",
        "blocking_reasons",
    ],
    "properties": {
        "answer_ko": {"type": "string", "maxLength": 600},
        "answer_en": {"type": "string", "maxLength": 600},
        "cited_packet_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "fact_vs_interpretation_map": {
            "type": "object",
            "additionalProperties": {"enum": ["fact", "interpretation"]},
        },
        "recheck_rule": {"type": "string"},
        "blocking_reasons": {"type": "array", "items": {"type": "string"}},
    },
}


# OpenAI ``response_format.json_schema`` with ``strict: true`` accepts only a
# limited JSON Schema subset: every property must be in ``required``,
# ``additionalProperties`` must be ``false`` on every object, keywords like
# ``maxLength`` / ``minItems`` are not supported, and open-keyed maps (i.e.
# ``additionalProperties: <schema>``) are not allowed.  We therefore expose a
# strict-safe variant that represents ``fact_vs_interpretation_map`` as an
# array of ``{packet_id, label}`` objects.  ``OpenAIProvider`` unfolds the
# array back into a dict before returning, so the internal Pydantic contract
# is unchanged.
OPENAI_STRICT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer_ko",
        "answer_en",
        "cited_packet_ids",
        "fact_vs_interpretation",
        "recheck_rule",
        "blocking_reasons",
    ],
    "properties": {
        "answer_ko": {"type": "string"},
        "answer_en": {"type": "string"},
        "cited_packet_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "fact_vs_interpretation": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["packet_id", "label"],
                "properties": {
                    "packet_id": {"type": "string"},
                    "label": {"type": "string", "enum": ["fact", "interpretation"]},
                },
            },
        },
        "recheck_rule": {"type": "string"},
        "blocking_reasons": {"type": "array", "items": {"type": "string"}},
    },
}
