"""LLM provider abstraction.

Three providers, all returning a dict compatible with
``LLMResponseContractV1``:

  * ``FixtureProvider``   - deterministic, used in tests and fixture mode.
  * ``OpenAIProvider``    - real OpenAI API call with JSON schema enforcement.
  * ``AnthropicProvider`` - real Anthropic API call using JSON tool use.

Provider selection:
  ``METIS_HARNESS_LLM_PROVIDER`` env var, one of ``fixture|openai|anthropic``.
  If unset the fixture provider is used so tests and evidence generation
  never touch the network by accident.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from agentic_harness.llm.contract import (
    OPENAI_STRICT_RESPONSE_SCHEMA,
    RESPONSE_JSON_SCHEMA,
)


class LLMProviderError(RuntimeError):
    pass


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    state_bundle: dict[str, Any]
    allowed_packet_ids: list[str]


class LLMProviderProtocol(Protocol):
    provider_name: str

    def complete(self, req: LLMRequest) -> dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# FixtureProvider
# ---------------------------------------------------------------------------


class FixtureProvider:
    """Deterministic provider used in tests and fixture CLI.

    Echoes back the state bundle into the contract shape so tests can assert
    on deterministic answers without hitting a live model.
    """

    provider_name = "fixture"

    def __init__(self, *, override_response: Optional[dict[str, Any]] = None) -> None:
        self._override = override_response

    def complete(self, req: LLMRequest) -> dict[str, Any]:
        if self._override is not None:
            return dict(self._override)
        cited = list(req.allowed_packet_ids)[:3] or ["packet:none"]
        routed_kind = str(req.state_bundle.get("routed_kind") or "why_changed")
        asset_id = str(req.state_bundle.get("asset_id") or "")
        ko = (
            f"[fixture] 요청된 자산 {asset_id}에 대한 질문 유형={routed_kind} 에 "
            "대해 현재 레지스트리 상태와 최근 overlay/연구 packet 을 그대로 요약합니다. "
            "해석 라벨은 cited packet 별로 명시되어 있습니다."
        )
        en = (
            f"[fixture] Summary for asset {asset_id} (routed={routed_kind}): "
            "current registry state and the most recent overlay/research packets "
            "are echoed verbatim; interpretation labels are attached per cited packet."
        )
        return {
            "answer_ko": ko[:600],
            "answer_en": en[:600],
            "cited_packet_ids": cited,
            "fact_vs_interpretation_map": {pid: "interpretation" for pid in cited},
            "recheck_rule": "recheck_next_harness_tick",
            "blocking_reasons": [],
        }


# ---------------------------------------------------------------------------
# OpenAIProvider / AnthropicProvider - imported only if selected, so tests
# never import the network SDKs accidentally.
# ---------------------------------------------------------------------------


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, *, model: str = "gpt-4o-mini") -> None:
        api_key = os.getenv("OPENAI_API_KEY") or ""
        if not api_key.strip():
            raise LLMProviderError("OPENAI_API_KEY not configured")
        self._model = model
        self._api_key = api_key.strip()

    def complete(self, req: LLMRequest) -> dict[str, Any]:
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise LLMProviderError(f"openai package not available: {e}") from e
        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "LLMResponseContractV1",
                    "schema": OPENAI_STRICT_RESPONSE_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0.0,
        )
        try:
            content = resp.choices[0].message.content or "{}"
            raw = dict(json.loads(content))
        except Exception as e:
            raise LLMProviderError(f"invalid OpenAI response: {e}") from e
        # OpenAI strict mode returns ``fact_vs_interpretation`` as an array of
        # ``{packet_id, label}`` objects; fold it back to the dict shape that
        # ``LLMResponseContractV1`` expects.  Unknown labels are dropped so the
        # Pydantic validator can enforce its own Literal type.
        fact_map: dict[str, str] = {}
        for item in raw.get("fact_vs_interpretation") or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("packet_id") or "").strip()
            lbl = str(item.get("label") or "").strip()
            if pid and lbl in ("fact", "interpretation"):
                fact_map[pid] = lbl
        return {
            "answer_ko": str(raw.get("answer_ko") or ""),
            "answer_en": str(raw.get("answer_en") or ""),
            "cited_packet_ids": list(raw.get("cited_packet_ids") or []),
            "fact_vs_interpretation_map": fact_map,
            "recheck_rule": str(raw.get("recheck_rule") or ""),
            "blocking_reasons": list(raw.get("blocking_reasons") or []),
        }


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(self, *, model: str = "claude-3-5-haiku-latest") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        if not api_key.strip():
            raise LLMProviderError("ANTHROPIC_API_KEY not configured")
        self._model = model
        self._api_key = api_key.strip()

    def complete(self, req: LLMRequest) -> dict[str, Any]:
        try:
            import anthropic  # type: ignore
        except Exception as e:
            raise LLMProviderError(f"anthropic package not available: {e}") from e
        client = anthropic.Anthropic(api_key=self._api_key)
        tool = {
            "name": "return_response",
            "description": "Return the bounded response contract.",
            "input_schema": RESPONSE_JSON_SCHEMA,
        }
        msg = client.messages.create(
            model=self._model,
            system=req.system_prompt,
            messages=[{"role": "user", "content": req.user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "return_response"},
            max_tokens=1024,
            temperature=0.0,
        )
        try:
            for block in msg.content:
                if getattr(block, "type", "") == "tool_use":
                    return dict(block.input or {})
            raise LLMProviderError("no tool_use block returned")
        except Exception as e:
            raise LLMProviderError(f"invalid Anthropic response: {e}") from e


def select_provider(name: Optional[str] = None) -> LLMProviderProtocol:
    raw = str(name or os.getenv("METIS_HARNESS_LLM_PROVIDER") or "fixture").strip().lower()
    if raw == "openai":
        return OpenAIProvider()
    if raw == "anthropic":
        return AnthropicProvider()
    return FixtureProvider()
