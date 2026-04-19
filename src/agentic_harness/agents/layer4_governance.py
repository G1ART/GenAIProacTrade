"""Layer 4 - Model Quality Verification & Improvement (Governance).

Four deterministic agents operating strictly in **proposal mode**. This
layer never writes to the active registry, the brain bundle, or the
factor-validation tables - that remains the responsibility of the
governed `build-metis-brain-bundle-from-factor-validation` CLI run by a
human operator.

    * ``validation_referee_agent`` - decides whether a horizon's
      ``horizon_state_v1`` is eligible for a state transition.
    * ``promotion_arbiter_agent`` - runs the four deterministic gates
      (PIT, monotonicity, coverage, runtime explainability) on each
      transition candidate and emits a ``PromotionGatePacketV1``.
    * ``fallback_honesty_agent`` - when a gate fails, emits a
      ``RegistryUpdateProposalV1`` to degrade the state honestly (e.g.
      ``real_derived → real_derived_with_degraded_challenger`` or
      ``template_fallback → insufficient_evidence``).
    * ``regression_watcher_agent`` - compares the latest cycle to the
      previous one and emits an ``EvaluationPacketV1`` if a previously
      promoted horizon has regressed.

The four gate steps are deterministic booleans supplied as a
``gate_decision_input`` so tests can drive every path.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    EvaluationPacketV1,
    HORIZON_STATE_VALUES,
    PromotionGatePacketV1,
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError


# A "gate decision input" is the deterministic bundle that the operator
# (or, in the future, a bounded sub-agent) hands to Layer 4 for a given
# transition candidate. It is intentionally narrow so the layer's
# behaviour stays observable from tests.
#
#   horizon:          one of HORIZON_STATE_VALUES keys ("short" | "medium" | ...)
#   from_state:       current horizon state in the registry
#   proposed_state:   the target horizon state
#   gate_booleans:    {pit: bool, monotonicity: bool, coverage: bool,
#                     runtime_explainability: bool}
#   evidence_refs:    pointers to validation runs / panels backing the call


GateDecisionProvider = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
"""(store, now_iso) -> list of gate-decision input dicts."""

RegressionProvider = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
"""(store, now_iso) -> list of regression candidate dicts."""


_GATE_DECISION_PROVIDER: Optional[GateDecisionProvider] = None
_REGRESSION_PROVIDER: Optional[RegressionProvider] = None


def set_gate_decision_provider(fn: Optional[GateDecisionProvider]) -> None:
    global _GATE_DECISION_PROVIDER
    _GATE_DECISION_PROVIDER = fn


def set_regression_provider(fn: Optional[RegressionProvider]) -> None:
    global _REGRESSION_PROVIDER
    _REGRESSION_PROVIDER = fn


def _default_gate_provider(store, now_iso):
    return []


def _default_regression_provider(store, now_iso):
    return []


# ---------------------------------------------------------------------------
# Helper: deterministic downgrade table. Layer 4 will never propose a
# "silent failure" state; it picks the most honest representation the spec
# allows.
# ---------------------------------------------------------------------------


def _honest_fallback_state(
    *, from_state: str, proposed_state: str
) -> str:
    """Returns the honest state to downgrade to when a gate fails.

    Preserves the canonical 4-value vocabulary of ``horizon_state_v1``
    from BNCO-6.
    """

    if proposed_state == "real_derived":
        return "real_derived_with_degraded_challenger"
    if proposed_state == "real_derived_with_degraded_challenger":
        return "template_fallback"
    # Fallbacks from template_fallback land in insufficient_evidence so
    # operators see the honest "we don't have enough signal" state.
    return "insufficient_evidence"


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def validation_referee_agent(
    store: HarnessStoreProtocol, now_iso: str
) -> list[dict[str, Any]]:
    """Returns the raw gate-decision input list (pass-through by design).

    In production this agent reads the current factor validation panel
    and brain bundle to decide which horizons should be re-evaluated.
    The harness keeps the read-side pluggable so tests can inject.
    """

    provider = _GATE_DECISION_PROVIDER or _default_gate_provider
    raw = provider(store, now_iso) or []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        from_state = str(row.get("from_state") or "")
        proposed = str(row.get("proposed_state") or "")
        if from_state not in HORIZON_STATE_VALUES or proposed not in HORIZON_STATE_VALUES:
            continue
        if from_state == proposed:
            continue
        out.append(row)
    return out


def _build_promotion_gate_packet(
    *,
    gate_input: dict[str, Any],
    now_iso: str,
) -> PromotionGatePacketV1:
    bools = dict(gate_input.get("gate_booleans") or {})
    steps = []
    all_pass = True
    for step_name in ("pit", "monotonicity", "coverage", "runtime_explainability"):
        ok = bool(bools.get(step_name, False))
        steps.append({"step": step_name, "outcome": "pass" if ok else "fail"})
        if not ok:
            all_pass = False
    overall = "pass" if all_pass else "fail"
    horizon = str(gate_input.get("horizon") or "")
    pid = deterministic_packet_id(
        packet_type="PromotionGatePacketV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={
            "horizon": horizon,
            "from_state": str(gate_input.get("from_state") or ""),
            "proposed_state": str(gate_input.get("proposed_state") or ""),
        },
        salt=now_iso,
    )
    provenance = list(gate_input.get("evidence_refs") or [f"governance://{horizon}"])
    return PromotionGatePacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "PromotionGatePacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "horizon": horizon,
                "from_state": str(gate_input.get("from_state") or ""),
                "proposed_state": str(gate_input.get("proposed_state") or ""),
            },
            "provenance_refs": provenance,
            "confidence": 0.9 if all_pass else 0.5,
            "payload": {
                "candidate_ref": str(gate_input.get("candidate_ref") or f"governance://{horizon}"),
                "gate_steps": steps,
                "overall_outcome": overall,
            },
        }
    )


def promotion_arbiter_agent(
    *, gate_inputs: list[dict[str, Any]], now_iso: str
) -> list[PromotionGatePacketV1]:
    return [
        _build_promotion_gate_packet(gate_input=gi, now_iso=now_iso) for gi in gate_inputs
    ]


def _build_update_proposal(
    *,
    gate_input: dict[str, Any],
    target_state: str,
    gate_packet_id: str,
    now_iso: str,
    extra_blocking_reasons: Optional[list[str]] = None,
) -> RegistryUpdateProposalV1:
    horizon = str(gate_input.get("horizon") or "")
    from_state = str(gate_input.get("from_state") or "")
    provenance = list(gate_input.get("evidence_refs") or [f"governance://{horizon}"])
    provenance.append(f"packet:{gate_packet_id}")
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={
            "horizon": horizon,
            "from_state": from_state,
            "to_state": target_state,
        },
        salt=now_iso,
    )
    return RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "horizon": horizon,
                "from_state": from_state,
                "to_state": target_state,
            },
            "provenance_refs": provenance,
            "confidence": 0.8,
            "blocking_reasons": list(extra_blocking_reasons or []),
            "payload": {
                "target": "horizon_provenance",
                "from_state": from_state,
                "to_state": target_state,
                "evidence_refs": list(gate_input.get("evidence_refs") or [f"governance://{horizon}"]),
                "horizon": horizon,
                "proposal_doctrine_note": (
                    "Proposal only. Registry write remains the responsibility of the "
                    "governed build-metis-brain-bundle-from-factor-validation CLI."
                ),
            },
        }
    )


def fallback_honesty_agent(
    *,
    gate_input: dict[str, Any],
    gate_packet: PromotionGatePacketV1,
    now_iso: str,
) -> RegistryUpdateProposalV1:
    proposed = str(gate_input.get("proposed_state") or "")
    target_state = _honest_fallback_state(
        from_state=str(gate_input.get("from_state") or ""),
        proposed_state=proposed,
    )
    failing_steps = [
        s["step"]
        for s in (gate_packet.payload or {}).get("gate_steps") or []
        if s.get("outcome") == "fail"
    ]
    blocking = [f"gate_fail:{s}" for s in failing_steps]
    return _build_update_proposal(
        gate_input=gate_input,
        target_state=target_state,
        gate_packet_id=gate_packet.packet_id,
        now_iso=now_iso,
        extra_blocking_reasons=blocking,
    )


def regression_watcher_agent(
    store: HarnessStoreProtocol, now_iso: str
) -> list[EvaluationPacketV1]:
    provider = _REGRESSION_PROVIDER or _default_regression_provider
    raw = provider(store, now_iso) or []
    out: list[EvaluationPacketV1] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        target_ref = str(r.get("target_ref") or "")
        metrics = dict(r.get("metrics") or {})
        pid = deterministic_packet_id(
            packet_type="EvaluationPacketV1",
            created_by_agent="regression_watcher_agent",
            target_scope={"target_ref": target_ref, "kind": "regression_detected"},
            salt=now_iso,
        )
        out.append(
            EvaluationPacketV1.model_validate(
                {
                    "packet_id": pid,
                    "packet_type": "EvaluationPacketV1",
                    "target_layer": "layer4_governance",
                    "created_by_agent": "regression_watcher_agent",
                    "target_scope": {
                        "target_ref": target_ref,
                        "kind": "regression_detected",
                    },
                    "provenance_refs": list(r.get("provenance_refs") or [target_ref or "regression"]),
                    "confidence": float(r.get("confidence", 0.7)),
                    "blocking_reasons": list(r.get("blocking_reasons") or []),
                    "payload": {
                        "evaluation_kind": "regression_detected",
                        "target_ref": target_ref,
                        "metrics": metrics,
                    },
                }
            )
        )
    return out


def propose_layer4_cadence(
    store: HarnessStoreProtocol, now_iso: str
) -> dict[str, Any]:
    gate_inputs = validation_referee_agent(store, now_iso)
    gate_packets = promotion_arbiter_agent(gate_inputs=gate_inputs, now_iso=now_iso)
    proposals: list[RegistryUpdateProposalV1] = []
    for gi, gp in zip(gate_inputs, gate_packets):
        store.upsert_packet(gp.model_dump())
        if gp.payload.get("overall_outcome") == "pass":
            target_state = str(gi.get("proposed_state") or "")
            proposal = _build_update_proposal(
                gate_input=gi,
                target_state=target_state,
                gate_packet_id=gp.packet_id,
                now_iso=now_iso,
            )
        else:
            proposal = fallback_honesty_agent(
                gate_input=gi, gate_packet=gp, now_iso=now_iso
            )
        store.upsert_packet(proposal.model_dump())
        proposals.append(proposal)
        # Enqueue into governance_queue so Layer 5 / operator can surface.
        job = QueueJobV1.model_validate(
            {
                "job_id": deterministic_job_id(
                    queue_class="governance_queue",
                    packet_id=proposal.packet_id,
                    salt=now_iso,
                ),
                "queue_class": "governance_queue",
                "packet_id": proposal.packet_id,
                "not_before_utc": now_iso,
                "worker_agent": "governance_inbox_worker",
            }
        )
        try:
            store.enqueue_job(job.model_dump())
        except StoreError:
            pass

    regression_packets = regression_watcher_agent(store, now_iso)
    for rp in regression_packets:
        store.upsert_packet(rp.model_dump())

    return {
        "gate_inputs": len(gate_inputs),
        "promotion_gate_packets": len(gate_packets),
        "registry_update_proposals": len(proposals),
        "proposal_outcomes": [
            {
                "from": p.payload.get("from_state"),
                "to": p.payload.get("to_state"),
            }
            for p in proposals
        ],
        "regression_events": len(regression_packets),
    }


# ---------------------------------------------------------------------------
# Queue worker: governance_queue -> surface_action_queue (escalation inbox)
# ---------------------------------------------------------------------------


def governance_queue_worker(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Escalates the ``RegistryUpdateProposalV1`` to
    ``surface_action_queue`` so the operator can see it in Today.

    The worker never touches the registry directly.
    """

    pid = str(job_row.get("packet_id") or "")
    pkt = store.get_packet(pid)
    if pkt is None:
        return {"ok": False, "error": f"packet_missing: {pid}"}
    store.set_packet_status(pid, "escalated")
    # Surface-action job is idempotent per proposal.
    sjob = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="surface_action_queue",
                packet_id=pid,
                salt="escalate",
            ),
            "queue_class": "surface_action_queue",
            "packet_id": pid,
            "worker_agent": "operator_inbox",
        }
    )
    try:
        store.enqueue_job(sjob.model_dump())
    except StoreError:
        pass
    return {"ok": True, "escalated_packet_id": pid, "surface_job_id": sjob.job_id}
