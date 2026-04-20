"""``LLMResponseContractV1`` - the only shape Layer 5 surfaces back to users.

Free-form LLM text is rejected at two levels:

  1. JSON schema enforcement (this module).
  2. Forbidden-copy guardrails (``guardrails.py``).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


FactVsInterpretation = Literal["fact", "interpretation"]

# AGH v1 Patch 5 extends USER_QUESTION_KINDS to include the Research ask
# intents (``deeper_rationale`` / ``what_remains_unproven`` /
# ``what_to_watch``) plus the explicit sandbox gating intent
# (``sandbox_request``). The canonical source of truth is
# ``agentic_harness.contracts.packets_v1.USER_QUESTION_KINDS``; we keep a
# mirror here so ``layer5_orchestrator`` does not import the full packet
# graph for this single constant and Patch 4 call sites stay unchanged.
USER_QUESTION_KINDS = (
    "why_changed",
    "system_status",
    "research_pending",
    "deeper_rationale",
    "what_remains_unproven",
    "what_to_watch",
    "sandbox_request",
)

# Mirror of ``agentic_harness.contracts.packets_v1.SANDBOX_KINDS``. Patch 5
# supports only ``validation_rerun`` (Workorder §3 / §5.C).
SANDBOX_KINDS = ("validation_rerun",)

# Research-answer intents that justify the structured research extension
# payload. Other kinds (``system_status`` / ``why_changed``) continue to
# ride the plain response contract.
RESEARCH_STRUCTURED_KINDS = (
    "deeper_rationale",
    "what_remains_unproven",
    "what_to_watch",
    "sandbox_request",
)


class ResearchAnswerStructureV1(BaseModel):
    """AGH v1 Patch 5 - structured research answer extension.

    Attached to ``LLMResponseContractV1.research_structured_v1`` when the
    routed intent is one of ``RESEARCH_STRUCTURED_KINDS``. The extension
    carries bounded bullet lists + a single optional
    ``proposed_sandbox_request`` so Layer 5 can surface a "file a sandbox
    rerun" CTA without ever emitting a raw registry mutation.

    Strict invariants (enforced by validators):
      * ``evidence_cited`` is a subset of the enclosing contract's
        ``cited_packet_ids`` (the enclosing contract cross-checks; this
        class only shape-validates its own keys).
      * ``proposed_sandbox_request.sandbox_kind`` must be in
        ``SANDBOX_KINDS``.
      * ``proposed_sandbox_request.target_spec`` must contain the
        Patch 5 required fields for ``validation_rerun``.
    """

    summary_bullets_ko: list[str] = Field(default_factory=list, max_length=6)
    summary_bullets_en: list[str] = Field(default_factory=list, max_length=6)
    residual_uncertainty_bullets: list[str] = Field(default_factory=list, max_length=6)
    what_to_watch_bullets: list[str] = Field(default_factory=list, max_length=6)
    evidence_cited: list[str] = Field(default_factory=list)
    proposed_sandbox_request: Optional[dict[str, Any]] = None

    @field_validator(
        "summary_bullets_ko",
        "summary_bullets_en",
        "residual_uncertainty_bullets",
        "what_to_watch_bullets",
    )
    @classmethod
    def _non_empty_bullets(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("bullets must be a list")
        out: list[str] = []
        for b in v:
            s = str(b or "").strip()
            if not s:
                continue
            if len(s) > 280:
                raise ValueError("each bullet must be <= 280 chars")
            out.append(s)
        return out

    @field_validator("evidence_cited")
    @classmethod
    def _evidence_cited_strings(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("evidence_cited must be a list")
        return [str(x).strip() for x in v if str(x or "").strip()]

    @field_validator("proposed_sandbox_request")
    @classmethod
    def _validate_proposed_sandbox_request(
        cls, v: Optional[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("proposed_sandbox_request must be a dict or null")
        for k in (
            "sandbox_kind",
            "registry_entry_id",
            "horizon",
            "target_spec",
            "rationale",
        ):
            if k not in v:
                raise ValueError(
                    f"proposed_sandbox_request requires '{k}'"
                )
        kind = v["sandbox_kind"]
        if kind not in SANDBOX_KINDS:
            raise ValueError(
                f"proposed_sandbox_request.sandbox_kind must be one of {SANDBOX_KINDS}"
            )
        target_spec = v["target_spec"]
        if not isinstance(target_spec, dict):
            raise ValueError("proposed_sandbox_request.target_spec must be a dict")
        if kind == "validation_rerun":
            for k in ("factor_name", "universe_name", "horizon_type", "return_basis"):
                if not str(target_spec.get(k) or "").strip():
                    raise ValueError(
                        f"proposed_sandbox_request.target_spec(validation_rerun) "
                        f"requires non-empty '{k}'"
                    )
        rationale = str(v.get("rationale") or "").strip()
        if not rationale:
            raise ValueError("proposed_sandbox_request.rationale must be non-empty")
        if len(rationale) > 500:
            raise ValueError("proposed_sandbox_request.rationale must be <= 500 chars")
        return dict(v)


class LLMResponseContractV1(BaseModel):
    contract: str = "METIS_AGENTIC_HARNESS_LLM_RESPONSE_V1"

    answer_ko: str = Field(max_length=600)
    answer_en: str = Field(max_length=600)
    cited_packet_ids: list[str] = Field(default_factory=list)
    fact_vs_interpretation_map: dict[str, FactVsInterpretation] = Field(default_factory=dict)
    recheck_rule: str = Field(default="")
    blocking_reasons: list[str] = Field(default_factory=list)

    # AGH v1 Patch 5 — optional structured research-answer extension. Set
    # by the orchestrator only for ``RESEARCH_STRUCTURED_KINDS`` intents.
    research_structured_v1: Optional[ResearchAnswerStructureV1] = None

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
        rs = self.research_structured_v1
        if rs is not None and rs.evidence_cited:
            missing = [pid for pid in rs.evidence_cited if pid not in cited]
            if missing:
                raise ValueError(
                    "research_structured_v1.evidence_cited must be a subset of "
                    f"cited_packet_ids; unknown refs: {missing}"
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
