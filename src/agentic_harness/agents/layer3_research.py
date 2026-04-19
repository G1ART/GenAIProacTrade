"""Layer 3 - Research Engine / Periodic Challenger Cycle.

Reuses the bounded ``PersonaCandidatePacketV1`` harness from
``src/metis_brain/persona_candidates_v1.py`` so this layer does not invent
a new research vocabulary. Every candidate the layer emits is wrapped in a
``ResearchCandidatePacketV1`` and an ``EvaluationPacket``-producing job is
enqueued on ``research_queue`` for Layer 4.

Three agents:

    * ``persona_challenger_agents`` - calls the underlying persona harness.
    * ``skeptic_falsification_analyst_agent`` - adds ``no_counter_interpretation``
      to ``blocking_reasons`` if the embedded persona packet did not include
      an explicit ``countercase``.
    * ``meta_governor_agent`` - dedupes on
      ``(intended_overlay_type, target_scope)``, rate-limits to 3 per cycle,
      and enqueues ``research_queue`` jobs for downstream evaluation.

Active registry / overlay seed / factor validation rows are **not** mutated.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    ResearchCandidatePacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError
from metis_brain.persona_candidates_v1 import (
    PersonaCandidatePacketV1,
    build_persona_candidate_packet,
)


PersonaCandidateFactory = Callable[[], list[dict[str, Any]]]
"""() -> list of dicts compatible with ``build_persona_candidate_packet``."""


_PERSONA_FACTORY: Optional[PersonaCandidateFactory] = None
_MAX_CANDIDATES_PER_CYCLE = 3


def set_persona_candidate_factory(fn: Optional[PersonaCandidateFactory]) -> None:
    global _PERSONA_FACTORY
    _PERSONA_FACTORY = fn


def _default_persona_factory() -> list[dict[str, Any]]:
    """By default, use the same demo harness as ``emit-persona-candidates``.

    Imported lazily so ``main.py`` is loaded only when we actually need a
    production-like persona stream (tests inject their own factory).
    """

    try:
        from main import _default_persona_candidate_demo  # type: ignore
    except Exception:
        return []
    try:
        return list(_default_persona_candidate_demo())
    except Exception:
        return []


def persona_challenger_agents(
    factory: Optional[PersonaCandidateFactory] = None,
) -> list[PersonaCandidatePacketV1]:
    f = factory or _PERSONA_FACTORY or _default_persona_factory
    specs = f() or []
    out: list[PersonaCandidatePacketV1] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        try:
            out.append(
                build_persona_candidate_packet(
                    persona=str(spec.get("persona", "")),
                    thesis_family=str(spec.get("thesis_family", "")),
                    targeted_horizon=str(spec.get("targeted_horizon", "short")),
                    targeted_universe=str(spec.get("targeted_universe", "")),
                    evidence_refs=list(spec.get("evidence_refs") or []),
                    confidence=float(spec.get("confidence", 0.5)),
                    overlay_recommendation=str(spec.get("overlay_recommendation", "")),
                    countercase=str(spec.get("countercase", "")),
                    gate_eligibility=dict(spec.get("gate_eligibility") or {}),
                    provenance_summary=str(spec.get("provenance_summary", "")),
                    signal_type=str(spec.get("signal_type", "")),
                    intended_overlay_type=str(spec.get("intended_overlay_type", "")),
                    blocking_reasons=list(spec.get("blocking_reasons") or []),
                )
            )
        except Exception:
            continue
    return out


def skeptic_falsification_analyst_agent(
    persona_packets: list[PersonaCandidatePacketV1],
) -> list[PersonaCandidatePacketV1]:
    patched: list[PersonaCandidatePacketV1] = []
    for pc in persona_packets:
        has_counter = bool(str(pc.countercase or "").strip())
        blocking = list(pc.blocking_reasons or [])
        if not has_counter and "no_counter_interpretation" not in blocking:
            blocking.append("no_counter_interpretation")
        patched.append(pc.model_copy(update={"blocking_reasons": blocking}))
    return patched


def _wrap_into_research_packet(
    pc: PersonaCandidatePacketV1,
) -> ResearchCandidatePacketV1:
    tgt_scope = {
        "persona": pc.persona,
        "targeted_horizon": pc.targeted_horizon,
        "targeted_universe": pc.targeted_universe,
        "intended_overlay_type": pc.intended_overlay_type or "",
    }
    pid = deterministic_packet_id(
        packet_type="ResearchCandidatePacketV1",
        created_by_agent="persona_challenger_agent",
        target_scope=tgt_scope,
        salt=str(pc.candidate_id),
    )
    provenance = [f"persona_candidate:{pc.candidate_id}"]
    for ref in pc.evidence_refs or []:
        pointer = str(getattr(ref, "pointer", "") or "").strip()
        if pointer:
            provenance.append(pointer)
    return ResearchCandidatePacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "ResearchCandidatePacketV1",
            "target_layer": "layer3_research",
            "created_by_agent": "persona_challenger_agent",
            "target_scope": tgt_scope,
            "provenance_refs": provenance,
            "confidence": float(pc.confidence),
            "blocking_reasons": list(pc.blocking_reasons or []),
            "payload": {
                "persona_candidate_packet": pc.model_dump(),
                "signal_type": pc.signal_type or "",
                "intended_overlay_type": pc.intended_overlay_type or "",
            },
        }
    )


def meta_governor_agent(
    *,
    store: HarnessStoreProtocol,
    research_packets: list[ResearchCandidatePacketV1],
    now_iso: str,
    max_per_cycle: int = _MAX_CANDIDATES_PER_CYCLE,
) -> dict[str, Any]:
    deduped: list[ResearchCandidatePacketV1] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for rp in research_packets:
        ts = rp.target_scope or {}
        key = (
            str(ts.get("persona") or ""),
            str(ts.get("targeted_horizon") or ""),
            str(ts.get("targeted_universe") or ""),
            str(ts.get("intended_overlay_type") or ""),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(rp)
        if len(deduped) >= int(max_per_cycle):
            break
    enqueued_jobs: list[str] = []
    for rp in deduped:
        store.upsert_packet(rp.model_dump())
        job = QueueJobV1.model_validate(
            {
                "job_id": deterministic_job_id(
                    queue_class="research_queue",
                    packet_id=rp.packet_id,
                    salt=now_iso,
                ),
                "queue_class": "research_queue",
                "packet_id": rp.packet_id,
                "not_before_utc": now_iso,
                "worker_agent": "meta_governor_worker",
            }
        )
        try:
            store.enqueue_job(job.model_dump())
            enqueued_jobs.append(job.job_id)
        except StoreError:
            pass
    return {
        "candidates_total": len(research_packets),
        "candidates_after_dedupe": len(deduped),
        "enqueued_jobs": enqueued_jobs,
    }


def propose_layer3_cadence(
    store: HarnessStoreProtocol, now_iso: str
) -> dict[str, Any]:
    personas = persona_challenger_agents()
    personas = skeptic_falsification_analyst_agent(personas)
    research_packets = [_wrap_into_research_packet(pc) for pc in personas]
    return meta_governor_agent(
        store=store, research_packets=research_packets, now_iso=now_iso
    )


# ---------------------------------------------------------------------------
# Queue worker: research_queue
# ---------------------------------------------------------------------------


def research_queue_worker(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Deterministic pass-through: the research queue exists so Layer 4 can
    pick up the candidate in its own cadence, rather than Layer 3 writing
    directly into governance. The worker marks the packet as ``done`` so
    it drops out of the active backlog.
    """

    pid = str(job_row.get("packet_id") or "")
    pkt = store.get_packet(pid)
    if pkt is None:
        return {"ok": False, "error": f"packet_missing: {pid}"}
    store.set_packet_status(pid, "done")
    return {"ok": True, "triaged_packet_id": pid}
