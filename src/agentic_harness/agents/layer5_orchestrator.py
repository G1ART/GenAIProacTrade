"""Layer 5 - Bounded user-surface LLM orchestrator.

Three agents:

    * ``action_router_agent``   - keyword classifier that routes a free-form
      user question into one of three canonical kinds
      (``why_changed`` / ``system_status`` / ``research_pending``).
    * ``state_reader_agent``    - deterministic state compiler. Reads the
      harness store + Today registry + recent overlay/research packets and
      builds the structured input the LLM is allowed to see.
    * ``founder_user_orchestrator_agent`` - calls the LLM provider with the
      structured input and applies guardrails + JSON schema enforcement.
      On any violation it falls back to a deterministic template and sets
      ``llm_fallback=true``.

The final ``UserQueryActionPacketV1`` captures the entire round trip so
auditors can replay exactly what the user was told and why.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import ValidationError

from agentic_harness.contracts.packets_v1 import (
    UserQueryActionPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.llm.contract import LLMResponseContractV1, USER_QUESTION_KINDS
from agentic_harness.llm.guardrails import (
    guardrail_violations,
    redact_forbidden,
    redact_mapping,
    validate_cited_ids_subset,
)
from agentic_harness.llm.provider import (
    FixtureProvider,
    LLMProviderError,
    LLMProviderProtocol,
    LLMRequest,
    select_provider,
)
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError


# ---------------------------------------------------------------------------
# Action Router
# ---------------------------------------------------------------------------


_ROUTING_RULES: list[tuple[str, tuple[str, ...]]] = [
    # (routed_kind, keyword_list)
    (
        "why_changed",
        ("왜", "바뀌", "변동", "why", "changed", "move", "움직", "어째서"),
    ),
    (
        "system_status",
        ("상태", "status", "큐", "queue", "packet", "system"),
    ),
    (
        "research_pending",
        ("연구", "research", "pending", "candidate", "후보", "대기"),
    ),
]


def action_router_agent(question: str) -> str:
    q = str(question or "").strip().lower()
    for kind, kws in _ROUTING_RULES:
        for kw in kws:
            if kw.lower() in q:
                return kind
    return "why_changed"  # default: treat unknown as "why changed"


# ---------------------------------------------------------------------------
# State Reader
# ---------------------------------------------------------------------------


def state_reader_agent(
    *, store: HarnessStoreProtocol, asset_id: str, routed_kind: str
) -> dict[str, Any]:
    """Compile the structured state bundle the LLM is allowed to see.

    The bundle is deterministic, bounded, and never includes free-form text
    from anywhere except controlled locale / seed JSON (which the caller
    may have baked into the packet payloads themselves).
    """

    asset_id = str(asset_id or "").upper().strip()
    relevant_packets: list[dict[str, Any]] = []

    def _collect(
        packet_type: str,
        layer: Optional[str],
        limit: int = 20,
        *,
        allow_asset_neutral: bool = False,
        status_in: Optional[tuple[str, ...]] = None,
    ) -> None:
        """Read packets for ``packet_type`` and append to ``relevant_packets``.

        Scope rules:
        * If ``asset_id`` is set, packets whose ``target_scope.asset_id``
          matches are always included.
        * ``allow_asset_neutral`` permits packets that do NOT carry an
          ``asset_id`` (e.g. universe-level research candidates or overlay
          proposals) to be included even when ``asset_id`` is set.  This is
          how Layer 5 surfaces pending research / why_changed context that
          applies across the registry rather than a single ticker.
        * When ``asset_id`` is empty, every row is relevant (system-wide
          queries).
        * ``status_in`` optionally filters packet rows by their top-level
          ``status`` field. AGH v1 Patch 2 uses this to hide proposals
          whose terminal state has rolled forward (e.g. the proposal moved
          to ``applied`` and the RegistryPatchAppliedPacketV1 is now the
          authoritative citation for that transition).
        """

        rows = store.list_packets(
            packet_type=packet_type, target_layer=layer, limit=limit
        )
        for r in rows:
            if status_in is not None:
                st = str(r.get("status") or "")
                if st not in status_in:
                    continue
            scope = r.get("target_scope") or {}
            scope_asset = str(scope.get("asset_id") or "").upper().strip()
            if asset_id and scope_asset == asset_id:
                relevant_packets.append(r)
            elif asset_id and not scope_asset and allow_asset_neutral:
                relevant_packets.append(r)
            elif not asset_id:
                relevant_packets.append(r)

    if routed_kind == "why_changed":
        # Per-asset evidence (IngestAlert / SourceArtifact) must be asset-scoped.
        # Registry-/universe-level signals (OverlayProposal /
        # RegistryUpdateProposal / ReplayLearning) may be asset-neutral and
        # still belong to the why-changed context so the LLM can explain them
        # as "signals to watch" rather than fabricating per-asset narratives.
        _collect("IngestAlertPacketV1", None, allow_asset_neutral=False)
        _collect("SourceArtifactPacketV1", None, allow_asset_neutral=False)
        _collect("OverlayProposalPacketV1", None, allow_asset_neutral=True)
        # AGH v1 Patch 2: only show proposals that are still in-flight as
        # "pending" signals. Once a proposal moves to ``applied``/``rejected``
        # the RegistryDecisionPacketV1 + RegistryPatchAppliedPacketV1 are the
        # authoritative citations the LLM should use.
        _collect(
            "RegistryUpdateProposalV1",
            None,
            allow_asset_neutral=True,
            status_in=("proposed", "escalated", "deferred"),
        )
        _collect(
            "RegistryDecisionPacketV1", None, allow_asset_neutral=True
        )
        _collect(
            "RegistryPatchAppliedPacketV1", None, allow_asset_neutral=True
        )
        # AGH v1 Patch 3: every registry_entry_artifact_promotion apply emits
        # a paired SpectrumRefreshRecordV1 whose payload explains whether the
        # spectrum rows were really recomputed or still reflect the prior
        # artifact (carry_over_*). The LLM needs this to decide whether the
        # rationale row copy is still valid.
        _collect(
            "SpectrumRefreshRecordV1", None, allow_asset_neutral=True
        )
        _collect("ReplayLearningPacketV1", None, allow_asset_neutral=True)
    elif routed_kind == "research_pending":
        # Research candidates are often universe-scoped (factor / gate /
        # cadence proposals).  Include them even when the user pins a
        # specific asset, so "pending research" never reads empty just
        # because the candidate wasn't tied to a ticker.
        _collect("ResearchCandidatePacketV1", None, allow_asset_neutral=True)
        _collect("EvaluationPacketV1", None, allow_asset_neutral=True)
        _collect("PromotionGatePacketV1", None, allow_asset_neutral=True)
    elif routed_kind == "system_status":
        # status is global; include a compact census rather than asset-scoped rows.
        relevant_packets = []

    depths = store.queue_depth()
    packet_counts = store.count_packets_by_layer()
    last_tick = store.last_tick_of_kind("harness_tick")

    return {
        "contract": "METIS_AGENTIC_HARNESS_STATE_BUNDLE_V1",
        "asset_id": asset_id,
        "routed_kind": routed_kind,
        "queue_depth": depths,
        "packet_counts_by_layer": packet_counts,
        "last_harness_tick_at_utc": (last_tick or {}).get("tick_at_utc"),
        "relevant_packets": relevant_packets,
    }


# ---------------------------------------------------------------------------
# Founder/User Orchestrator
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are a bounded operator agent inside the METIS Agentic Operating "
    "Harness v1. You must respond ONLY with a JSON object matching the "
    "LLMResponseContractV1 schema. You may only cite packet_ids that appear "
    "in the provided state bundle. You must NEVER use any of these tokens: "
    "'buy', 'sell', 'guaranteed', 'recommend', 'will definitely', '확실', "
    "'반드시 오른/내린', '무조건 오른/내린'. If the bundle does not justify "
    "a firm statement, mark the relevant fact_vs_interpretation entry as "
    "'interpretation' and add to blocking_reasons. "
    # AGH v1 Patch 2 — promotion bridge vocabulary.
    "RegistryUpdateProposalV1 packets carry a status: 'proposed' / 'escalated' "
    "means the registry has NOT changed yet and the item is a *pending proposal* "
    "or *signal to watch*; 'deferred' means a decision declined to apply for "
    "now; 'rejected' means the proposal was declined; 'applied' means the "
    "governed write has landed. "
    "You must NEVER claim that the Today registry has changed its active "
    "model family, active band, or active horizon_provenance.source UNLESS "
    "the cited packet is a RegistryPatchAppliedPacketV1 with payload.outcome "
    "== 'applied'. In that case you may describe the transition as an "
    "accomplished fact, but you must cite the RegistryPatchAppliedPacketV1 "
    "packet_id in cited_packet_ids and label it as 'fact' in "
    "fact_vs_interpretation_map. Otherwise describe new ingest alerts, "
    "pending research candidates, proposals, or operator decisions as "
    "*signals to watch*, *proposals*, or *pending operator-approved patches* "
    "— never as accomplished facts about the Today surface. "
    "The Today active state is only updated by the promotion gate + "
    "governed registry patch (RegistryPatchAppliedPacketV1), which is the "
    "sole authoritative signal of an applied change. "
    # AGH v1 Patch 3 — artifact promotion + spectrum refresh vocabulary.
    "RegistryUpdateProposalV1 and RegistryPatchAppliedPacketV1 can target "
    "two things: (a) 'horizon_provenance' state transitions, or (b) "
    "'registry_entry_artifact_promotion' — an active/challenger artifact "
    "swap on a registry_entry. When payload.target == "
    "'registry_entry_artifact_promotion' and payload.outcome == 'applied', "
    "you may state that the active model family / active artifact for that "
    "horizon has changed. However, you MUST also check the tightly-linked "
    "SpectrumRefreshRecordV1 (cited_applied_packet_id == the applied packet "
    "id): if its payload.needs_db_rebuild is true or its payload.outcome "
    "begins with 'carry_over_', the spectrum rationale rows still reflect "
    "the prior artifact and must be described as pending a full rebuild — "
    "do not claim the rationale text has already updated to the new "
    "artifact."
)


def _template_fallback_response(
    *,
    state_bundle: dict[str, Any],
    reason: str,
) -> LLMResponseContractV1:
    cited = [p.get("packet_id") for p in (state_bundle.get("relevant_packets") or [])][:3]
    cited = [c for c in cited if c]
    if not cited:
        cited = ["bundle:" + str(state_bundle.get("routed_kind") or "unknown")]
    ko = (
        "LLM 응답이 가드레일을 통과하지 못했거나 사용할 수 없어, "
        "현 상태를 결정적 템플릿으로 요약합니다. 해석 라벨은 전부 'interpretation' 입니다."
    )
    en = (
        "LLM response was blocked or unavailable; returning a deterministic "
        "state template. All interpretation labels are conservative."
    )
    return LLMResponseContractV1.model_validate(
        {
            "answer_ko": ko,
            "answer_en": en,
            "cited_packet_ids": cited,
            "fact_vs_interpretation_map": {c: "interpretation" for c in cited},
            "recheck_rule": "recheck_next_harness_tick",
            "blocking_reasons": [f"llm_fallback:{reason}"],
            "llm_fallback": True,
            "fallback_reason": str(reason or ""),
        }
    )


def _call_provider_safe(
    *,
    provider: LLMProviderProtocol,
    req: LLMRequest,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        raw = provider.complete(req)
        if not isinstance(raw, dict):
            return None, "provider_returned_non_dict"
        return raw, None
    except LLMProviderError as e:
        return None, f"provider_error:{e}"
    except Exception as e:
        return None, f"provider_exception:{e}"


def founder_user_orchestrator_agent(
    *,
    store: HarnessStoreProtocol,
    question: str,
    asset_id: str,
    lang: str = "ko",
    provider: Optional[LLMProviderProtocol] = None,
) -> dict[str, Any]:
    routed_kind = action_router_agent(question)
    state_bundle = state_reader_agent(
        store=store, asset_id=asset_id, routed_kind=routed_kind
    )
    allowed_packet_ids = [
        str(p.get("packet_id") or "") for p in state_bundle.get("relevant_packets") or []
    ]
    user_prompt = (
        "Question (verbatim): "
        + json.dumps(question, ensure_ascii=False)
        + "\nLang: "
        + str(lang or "ko")
        + "\nState bundle (read-only): "
        + json.dumps(state_bundle, ensure_ascii=False, default=str)
    )
    req = LLMRequest(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        state_bundle=state_bundle,
        allowed_packet_ids=allowed_packet_ids,
    )
    p = provider or select_provider()
    raw, err = _call_provider_safe(provider=p, req=req)

    guardrail_passed = True
    fallback_reason = ""
    if raw is None:
        response = _template_fallback_response(state_bundle=state_bundle, reason=err or "unknown")
        guardrail_passed = False
        fallback_reason = err or "provider_error"
    else:
        # 1) Guardrail on answer bodies.
        texts = [raw.get("answer_ko", ""), raw.get("answer_en", "")]
        violations = guardrail_violations(texts)
        if violations:
            # Do not echo the forbidden tokens themselves back into the
            # packet body; report a count-based category instead.
            response = _template_fallback_response(
                state_bundle=state_bundle,
                reason=f"forbidden_copy:count={len(set(violations))}",
            )
            guardrail_passed = False
            fallback_reason = response.fallback_reason
        else:
            # 2) Cited ids must be from the bundle.
            cited = list(raw.get("cited_packet_ids") or [])
            bogus = validate_cited_ids_subset(
                cited_packet_ids=cited,
                allowed_packet_ids=allowed_packet_ids,
            )
            if bogus:
                response = _template_fallback_response(
                    state_bundle=state_bundle,
                    reason=f"hallucinated_cited_ids:count={len(bogus)}",
                )
                guardrail_passed = False
                fallback_reason = response.fallback_reason
            else:
                # 3) Schema enforcement.
                try:
                    response = LLMResponseContractV1.model_validate(raw)
                except ValidationError as ve:
                    response = _template_fallback_response(
                        state_bundle=state_bundle,
                        reason=f"schema_violation:{ve.errors()[0].get('msg','')}",
                    )
                    guardrail_passed = False
                    fallback_reason = response.fallback_reason

    safe_payload = redact_mapping(
        {
            "question": question,
            "routed_kind": routed_kind,
            "state_bundle_refs": allowed_packet_ids
            or [f"bundle:{routed_kind}:{asset_id or 'GLOBAL'}"],
            "llm_response": response.model_dump(),
            "guardrail_passed": guardrail_passed,
            "fallback_reason": fallback_reason,
            "provider_name": getattr(p, "provider_name", "unknown"),
        }
    )
    packet = UserQueryActionPacketV1.model_validate(
        {
            "packet_id": deterministic_packet_id(
                packet_type="UserQueryActionPacketV1",
                created_by_agent="founder_user_orchestrator_agent",
                target_scope={"asset_id": asset_id, "routed_kind": routed_kind},
                salt=redact_forbidden(question)[:64],
            ),
            "packet_type": "UserQueryActionPacketV1",
            "target_layer": "layer5_surface",
            "created_by_agent": "founder_user_orchestrator_agent",
            "target_scope": {"asset_id": asset_id, "routed_kind": routed_kind},
            "provenance_refs": allowed_packet_ids
            or [f"bundle:{routed_kind}:{asset_id or 'GLOBAL'}"],
            "confidence": 0.6 if guardrail_passed else 0.2,
            "blocking_reasons": list(response.blocking_reasons),
            "payload": safe_payload,
        }
    )
    store.upsert_packet(packet.model_dump())
    # Enqueue a surface_action_queue entry so operators can see the exchange.
    sjob = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="surface_action_queue",
                packet_id=packet.packet_id,
            ),
            "queue_class": "surface_action_queue",
            "packet_id": packet.packet_id,
            "worker_agent": "operator_inbox",
        }
    )
    try:
        store.enqueue_job(sjob.model_dump())
    except StoreError:
        pass
    return {
        "user_query_action_packet_id": packet.packet_id,
        "routed_kind": routed_kind,
        "guardrail_passed": guardrail_passed,
        "response": response.model_dump(),
        "provider_name": getattr(p, "provider_name", "unknown"),
    }


def run_layer5_ask(
    *,
    store: HarnessStoreProtocol,
    asset_id: str,
    question: str,
    lang: str = "ko",
    provider_name: Optional[str] = None,
) -> dict[str, Any]:
    provider = select_provider(provider_name)
    return founder_user_orchestrator_agent(
        store=store,
        question=question,
        asset_id=asset_id,
        lang=lang,
        provider=provider,
    )
