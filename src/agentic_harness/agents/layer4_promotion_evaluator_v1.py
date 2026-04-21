"""Layer 4 upstream - Validation -> Governance Promotion Evaluator (AGH v1 Patch 4).

Turns completed ``factor_validation`` evidence into:

    * a deterministic challenger ``ModelArtifactPacketV0`` (via
      ``metis_brain.artifact_from_validation_v1.build_artifact_from_validation_v1``),
    * a metric-based ``PromotionGateRecordV0`` (via the ``factor_validation``
      adapter + ``metis_brain.validation_bridge_v0.promotion_gate_from_validation_summary``),
    * an automatic ``RegistryUpdateProposalV1(target='registry_entry_artifact_promotion')``
      when and only when the gate verdict is ``promote`` and the candidate
      artifact is not already the active one.

Every evaluation emits a ``ValidationPromotionEvaluationV1`` audit packet so
replay can reconstruct the full validation -> artifact -> gate -> proposal
chain upstream of the Patch 3 apply bridge.

Invariants (work-order METIS_Patch_4 §2, §3):

    * No direct active-state mutation. Swapping ``active_artifact_id`` stays
      gated behind ``harness-decide approve`` + Patch 3 ``registry_patch_executor``.
    * No LLM-authored registry write.
    * Canonical write path: ``validate_merged_bundle_dict`` + ``write_bundle_json_atomic``
      from ``metis_brain.bundle_promotion_merge_v0`` (same chain used by Patch
      2/3 apply). The evaluator writes to the bundle only when adding a new
      challenger slot or syncing an existing challenger's ``validation_pointer``
      and only after the mutated bundle passes integrity.
    * Honest non-promotion: if validation evidence is missing, the gate blocks,
      or the artifact is already active, the evaluation packet still fires but
      no proposal is generated.
    * Stable artifact id derivation: ``art_<factor>_<universe>_<horizon_type>_<return_basis>_<hex8(sha256(...))>``
      is deterministic in (factor, universe, horizon_type, return_basis,
      validation_run_id) so running the evaluator twice on the same validation
      evidence yields identical artifact + evaluation identities.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    REGISTRY_BUNDLE_HORIZONS,
    RegistryUpdateProposalV1,
    ValidationPromotionEvaluationV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError
from metis_brain.artifact_from_validation_v1 import (
    build_artifact_from_validation_v1,
    map_validation_horizon_to_bundle_horizon,
)
from metis_brain.bundle import brain_bundle_path
from metis_brain.bundle_promotion_merge_v0 import (
    load_bundle_json,
    merge_promotion_gate_into_bundle_dict,
    sync_artifact_validation_pointer_for_factor_run,
    validate_merged_bundle_dict,
    write_bundle_json_atomic,
)
from metis_brain.factor_validation_gate_adapter_v0 import (
    build_metis_gate_summary_from_factor_summary_row,
)
from metis_brain.validation_bridge_v0 import promotion_gate_from_validation_summary


log = logging.getLogger(__name__)


# Fetcher callables. The defaults bind to ``db.records`` (Supabase-backed);
# tests can inject fixture fetchers. Both are optional at the argument layer
# so fixture paths can skip importing supabase-dependent modules.
FetchValidationSummary = Callable[
    [Any, dict[str, Any]], tuple[Optional[str], list[dict[str, Any]]]
]
"""(client, spec) -> (run_id, rows).  ``spec`` carries factor/universe/horizon_type."""

FetchQuantiles = Callable[[Any, dict[str, Any]], list[dict[str, Any]]]
"""(client, spec) -> quantile rows.  ``spec`` carries run_id/factor/universe/horizon_type/return_basis."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root_from_env() -> Path:
    override = (os.environ.get("METIS_REPO_ROOT") or "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "mvp").exists():
            return parent
    return here.parents[3]


def derive_artifact_id(
    *,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
    validation_run_id: str,
) -> str:
    """Deterministic Patch 4 artifact id policy (choice B in the plan).

    ``art_<factor>_<universe>_<horizon_type>_<return_basis>_<hex8>``.
    The trailing ``hex8`` is derived from a pipe-joined encoding of the tuple
    plus ``validation_run_id`` so that (a) the same completed validation run
    always resolves to the same artifact id and (b) different return_basis or
    universe slots do not collide. The leading human-readable tokens make
    replay/inspection easier.
    """

    factor = str(factor_name or "").strip()
    universe = str(universe_name or "").strip()
    htype = str(horizon_type or "").strip()
    basis = str(return_basis or "raw").strip()
    rid = str(validation_run_id or "").strip()
    if not factor or not universe or not htype or not rid:
        raise ValueError(
            "derive_artifact_id requires factor_name/universe_name/horizon_type/validation_run_id"
        )
    joined = f"factor={factor}|universe={universe}|horizon_type={htype}|return_basis={basis}|run_id={rid}"
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]
    return f"art_{factor}_{universe}_{htype}_{basis}_{digest}"


def _derive_evaluation_id(
    *,
    registry_entry_id: str,
    horizon: str,
    derived_artifact_id: str,
    validation_run_id: str,
    now_iso: str,
) -> str:
    joined = (
        f"registry_entry={registry_entry_id}|horizon={horizon}|"
        f"artifact={derived_artifact_id}|run={validation_run_id}|now={now_iso}"
    )
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]
    return f"eval_{digest}"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _default_fetch_validation_summary(
    client: Any, spec: dict[str, Any]
) -> tuple[Optional[str], list[dict[str, Any]]]:
    from db.records import fetch_latest_factor_validation_summaries

    return fetch_latest_factor_validation_summaries(
        client,
        factor_name=str(spec["factor_name"]),
        universe_name=str(spec["universe_name"]),
        horizon_type=str(spec["horizon_type"]),
    )


def _default_fetch_quantiles(client: Any, spec: dict[str, Any]) -> list[dict[str, Any]]:
    from db.records import fetch_factor_quantiles_for_run

    return fetch_factor_quantiles_for_run(
        client,
        run_id=str(spec["run_id"]),
        factor_name=str(spec["factor_name"]),
        universe_name=str(spec["universe_name"]),
        horizon_type=str(spec["horizon_type"]),
        return_basis=str(spec["return_basis"]),
    )


def _find_registry_entry(
    bundle: dict[str, Any], *, registry_entry_id: str
) -> tuple[Optional[int], Optional[dict[str, Any]]]:
    entries = bundle.get("registry_entries") or []
    for i, e in enumerate(entries):
        if str((e or {}).get("registry_entry_id") or "") == registry_entry_id:
            return i, dict(e)
    return None, None


def _find_artifact(
    bundle: dict[str, Any], *, artifact_id: str
) -> Optional[dict[str, Any]]:
    for a in bundle.get("artifacts") or []:
        if str((a or {}).get("artifact_id") or "") == artifact_id:
            return dict(a)
    return None


def _gate_verdict_and_blocking_reasons(
    *, pit_pass: bool, coverage_pass: bool, monotonicity_pass: bool, gate_reasons: str
) -> tuple[str, list[str]]:
    """Deterministic Patch 4 verdict rule.

    ``reject``: ``pit_pass`` is False (aligns with
    ``METIS_Residual_Score_Semantics_v1.md`` invalidation rule
    ``factor_validation_pit_fail``).
    ``promote``: all three gates pass.
    ``hold``: PIT is fine but coverage or monotonicity blocks.
    """

    blocking: list[str] = []
    if not pit_pass:
        blocking.append("pit_failed")
    if not coverage_pass:
        blocking.append("coverage_insufficient")
    if not monotonicity_pass:
        blocking.append("monotonicity_inconclusive")

    if not pit_pass:
        verdict = "reject"
    elif pit_pass and coverage_pass and monotonicity_pass:
        verdict = "promote"
    else:
        verdict = "hold"

    if gate_reasons and gate_reasons.strip():
        blocking.append(f"gate_reasons={gate_reasons.strip()}")
    return verdict, blocking


def _append_unique(lst: list[str], item: str) -> list[str]:
    out = list(lst)
    if item not in out:
        out.append(item)
    return out


def _build_evaluation_packet(
    *,
    evaluation_id: str,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
    validation_run_id: str,
    validation_pointer: str,
    registry_entry_id: str,
    horizon: str,
    derived_artifact_id: str,
    artifact_action: str,
    gate_verdict: str,
    gate_metrics: dict[str, Any],
    blocking_reasons: list[str],
    outcome: str,
    emitted_proposal_packet_id: Optional[str],
    evidence_refs: list[str],
    now_iso: str,
) -> ValidationPromotionEvaluationV1:
    packet_id = deterministic_packet_id(
        packet_type="ValidationPromotionEvaluationV1",
        created_by_agent="promotion_evaluator_v1",
        target_scope={
            "evaluation_id": evaluation_id,
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
        },
        salt=now_iso,
    )
    payload: dict[str, Any] = {
        "evaluation_id": evaluation_id,
        "factor_name": factor_name,
        "universe_name": universe_name,
        "horizon_type": horizon_type,
        "return_basis": return_basis,
        "validation_run_id": validation_run_id,
        "validation_pointer": validation_pointer,
        "registry_entry_id": registry_entry_id,
        "horizon": horizon,
        "derived_artifact_id": derived_artifact_id,
        "artifact_action": artifact_action,
        "gate_verdict": gate_verdict,
        "gate_metrics": dict(gate_metrics),
        "outcome": outcome,
        "evidence_refs": list(evidence_refs),
    }
    if emitted_proposal_packet_id:
        payload["emitted_proposal_packet_id"] = emitted_proposal_packet_id
    else:
        payload["emitted_proposal_packet_id"] = None

    return ValidationPromotionEvaluationV1.model_validate(
        {
            "packet_id": packet_id,
            "packet_type": "ValidationPromotionEvaluationV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_evaluator_v1",
            "target_scope": {
                "evaluation_id": evaluation_id,
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
            },
            "provenance_refs": list(evidence_refs)
            or [f"factor_validation_run:{validation_run_id or 'unknown'}"],
            "confidence": (
                0.9
                if outcome == "proposal_emitted"
                else 0.5
                if outcome in ("blocked_by_gate", "blocked_same_as_active")
                else 0.3
            ),
            "blocking_reasons": list(blocking_reasons),
            "status": "done",
            "payload": payload,
        }
    )


def _emit_evaluation(
    store: HarnessStoreProtocol,
    packet: ValidationPromotionEvaluationV1,
) -> str:
    store.upsert_packet(packet.model_dump())
    return packet.packet_id


def _build_and_emit_proposal(
    store: HarnessStoreProtocol,
    *,
    registry_entry_id: str,
    horizon: str,
    from_active: str,
    to_active: str,
    from_challengers: list[str],
    to_challengers: list[str],
    evidence_refs: list[str],
    now_iso: str,
) -> str:
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_evaluator_v1",
        target_scope={
            "target": "registry_entry_artifact_promotion",
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
            "from_active_artifact_id": from_active,
            "to_active_artifact_id": to_active,
        },
        salt=now_iso,
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_evaluator_v1",
            "target_scope": {
                "target": "registry_entry_artifact_promotion",
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
            },
            "provenance_refs": list(evidence_refs),
            "confidence": 0.85,
            "blocking_reasons": [],
            "payload": {
                "target": "registry_entry_artifact_promotion",
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
                "from_active_artifact_id": from_active,
                "to_active_artifact_id": to_active,
                "from_challenger_artifact_ids": list(from_challengers),
                "to_challenger_artifact_ids": list(to_challengers),
                "evidence_refs": list(evidence_refs),
                "proposal_doctrine_note": (
                    "Proposal emitted automatically by promotion_evaluator_v1 "
                    "from completed factor_validation evidence. Operator decision "
                    "(harness-decide) still gates the actual registry apply."
                ),
            },
        }
    )
    store.upsert_packet(proposal.model_dump())

    # Ride the existing governance_queue so the decision flow is identical to
    # manual proposals emitted by propose_layer4_cadence.
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
        # idempotent: another tick may have already enqueued this proposal.
        pass
    return proposal.packet_id


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------


def evaluate_validation_for_promotion(
    *,
    store: HarnessStoreProtocol,
    bundle_path: Path,
    bundle_dict: dict[str, Any],
    registry_entry_id: str,
    horizon: str,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
    supabase_client: Optional[Any] = None,
    now_iso: Optional[str] = None,
    fetch_validation_summary: Optional[FetchValidationSummary] = None,
    fetch_quantiles: Optional[FetchQuantiles] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Evaluate a single ``(registry_entry_id, factor, universe, horizon, basis)``
    slot for potential artifact promotion.

    Returns a dict ``{evaluation_packet_id, outcome, gate_verdict,
    artifact_action, derived_artifact_id, emitted_proposal_packet_id?,
    blocking_reasons, dry_run_preview?}``.  In ``dry_run`` mode no bundle
    mutation occurs and no packets are persisted; the return describes what
    *would* happen.
    """

    now = str(now_iso or _now_iso())
    if horizon not in REGISTRY_BUNDLE_HORIZONS:
        raise ValueError(
            f"horizon must be one of {REGISTRY_BUNDLE_HORIZONS}, got {horizon!r}"
        )
    # Verify bundle horizon mapping matches the declared bundle horizon.
    try:
        mapped = map_validation_horizon_to_bundle_horizon(horizon_type)
    except ValueError:
        mapped = ""
    horizon_mapping_ok = bool(mapped) and mapped == horizon

    summary_fn = fetch_validation_summary or _default_fetch_validation_summary
    quant_fn = fetch_quantiles or _default_fetch_quantiles

    factor = str(factor_name or "").strip()
    universe = str(universe_name or "").strip()
    htype = str(horizon_type or "").strip()
    basis = str(return_basis or "raw").strip()

    # Look up the registry entry up front so every blocked outcome can still
    # cite the same slot.
    idx, entry = _find_registry_entry(
        bundle_dict, registry_entry_id=registry_entry_id
    )
    if entry is None:
        # Honest non-promotion: registry entry missing. This is not the same
        # as missing evidence, but from the evaluator's contract perspective
        # we cannot derive a meaningful before/after. Emit a missing_evidence
        # outcome with an explicit blocking reason so replay shows it.
        derived = derive_artifact_id(
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id="unknown",
        )
        eval_id = _derive_evaluation_id(
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            validation_run_id="unknown",
            now_iso=now,
        )
        ev = _build_evaluation_packet(
            evaluation_id=eval_id,
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id="unknown",
            validation_pointer="no_evidence",
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            artifact_action="no_change",
            gate_verdict="hold",
            gate_metrics={},
            blocking_reasons=[f"registry_entry_missing:{registry_entry_id}"],
            outcome="blocked_missing_evidence",
            emitted_proposal_packet_id=None,
            evidence_refs=[f"registry_entry_missing:{registry_entry_id}"],
            now_iso=now,
        )
        if not dry_run:
            _emit_evaluation(store, ev)
        return {
            "ok": True,
            "evaluation_packet_id": ev.packet_id,
            "outcome": "blocked_missing_evidence",
            "gate_verdict": "hold",
            "artifact_action": "no_change",
            "derived_artifact_id": derived,
            "emitted_proposal_packet_id": None,
            "blocking_reasons": list(ev.blocking_reasons or [])
            or [f"registry_entry_missing:{registry_entry_id}"],
            "dry_run": dry_run,
        }

    # --- Fetch validation evidence. ----------------------------------------
    try:
        run_id, rows = summary_fn(
            supabase_client,
            {
                "factor_name": factor,
                "universe_name": universe,
                "horizon_type": htype,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        log.warning("evaluator summary fetch failed: %s", exc)
        run_id, rows = None, []

    if not run_id or not rows:
        derived = derive_artifact_id(
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id="unknown",
        )
        eval_id = _derive_evaluation_id(
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            validation_run_id="unknown",
            now_iso=now,
        )
        ev = _build_evaluation_packet(
            evaluation_id=eval_id,
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id="unknown",
            validation_pointer="no_evidence",
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            artifact_action="no_change",
            gate_verdict="hold",
            gate_metrics={},
            blocking_reasons=[
                f"no_completed_factor_validation_summary:"
                f"factor={factor};universe={universe};horizon_type={htype}"
            ],
            outcome="blocked_missing_evidence",
            emitted_proposal_packet_id=None,
            evidence_refs=[
                f"factor_validation_run_missing:{factor}:{universe}:{htype}"
            ],
            now_iso=now,
        )
        if not dry_run:
            _emit_evaluation(store, ev)
        return {
            "ok": True,
            "evaluation_packet_id": ev.packet_id,
            "outcome": "blocked_missing_evidence",
            "gate_verdict": "hold",
            "artifact_action": "no_change",
            "derived_artifact_id": derived,
            "emitted_proposal_packet_id": None,
            "blocking_reasons": list(ev.blocking_reasons or []),
            "dry_run": dry_run,
        }

    row_by_basis = {str(r.get("return_basis") or ""): dict(r) for r in rows}
    if basis not in row_by_basis:
        derived = derive_artifact_id(
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id=str(run_id),
        )
        eval_id = _derive_evaluation_id(
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            validation_run_id=str(run_id),
            now_iso=now,
        )
        ev = _build_evaluation_packet(
            evaluation_id=eval_id,
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id=str(run_id),
            validation_pointer=f"factor_validation_run:{run_id}:{factor}:{basis}",
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            artifact_action="no_change",
            gate_verdict="hold",
            gate_metrics={},
            blocking_reasons=[
                f"return_basis_row_missing:requested={basis};available="
                f"{sorted(row_by_basis.keys())}"
            ],
            outcome="blocked_missing_evidence",
            emitted_proposal_packet_id=None,
            evidence_refs=[f"factor_validation_run:{run_id}"],
            now_iso=now,
        )
        if not dry_run:
            _emit_evaluation(store, ev)
        return {
            "ok": True,
            "evaluation_packet_id": ev.packet_id,
            "outcome": "blocked_missing_evidence",
            "gate_verdict": "hold",
            "artifact_action": "no_change",
            "derived_artifact_id": derived,
            "emitted_proposal_packet_id": None,
            "blocking_reasons": list(ev.blocking_reasons or []),
            "dry_run": dry_run,
        }

    summary_row = {**row_by_basis[basis], "run_id": str(run_id)}

    try:
        quantile_rows = quant_fn(
            supabase_client,
            {
                "run_id": str(run_id),
                "factor_name": factor,
                "universe_name": universe,
                "horizon_type": htype,
                "return_basis": basis,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        log.warning("evaluator quantile fetch failed: %s", exc)
        quantile_rows = []

    if not horizon_mapping_ok:
        # The bundle horizon we were asked to evaluate does not match the
        # declared validation horizon_type. Honest block: we will not mint
        # an artifact whose declared horizon disagrees with the registry
        # entry's horizon.
        derived = derive_artifact_id(
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id=str(run_id),
        )
        eval_id = _derive_evaluation_id(
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            validation_run_id=str(run_id),
            now_iso=now,
        )
        ev = _build_evaluation_packet(
            evaluation_id=eval_id,
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id=str(run_id),
            validation_pointer=f"factor_validation_run:{run_id}:{factor}:{basis}",
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived,
            artifact_action="no_change",
            gate_verdict="hold",
            gate_metrics={},
            blocking_reasons=[
                f"horizon_mismatch:bundle={horizon};validation_horizon_type={htype};"
                f"mapped_bundle_horizon={mapped or 'unknown'}"
            ],
            outcome="blocked_missing_evidence",
            emitted_proposal_packet_id=None,
            evidence_refs=[f"factor_validation_run:{run_id}"],
            now_iso=now,
        )
        if not dry_run:
            _emit_evaluation(store, ev)
        return {
            "ok": True,
            "evaluation_packet_id": ev.packet_id,
            "outcome": "blocked_missing_evidence",
            "gate_verdict": "hold",
            "artifact_action": "no_change",
            "derived_artifact_id": derived,
            "emitted_proposal_packet_id": None,
            "blocking_reasons": list(ev.blocking_reasons or []),
            "dry_run": dry_run,
        }

    derived_artifact_id = derive_artifact_id(
        factor_name=factor,
        universe_name=universe,
        horizon_type=htype,
        return_basis=basis,
        validation_run_id=str(run_id),
    )
    evaluation_id = _derive_evaluation_id(
        registry_entry_id=registry_entry_id,
        horizon=horizon,
        derived_artifact_id=derived_artifact_id,
        validation_run_id=str(run_id),
        now_iso=now,
    )
    validation_pointer = f"factor_validation_run:{run_id}:{factor}:{basis}"

    # --- Build candidate artifact + gate. ----------------------------------
    candidate_artifact = build_artifact_from_validation_v1(
        factor_name=factor,
        universe_name=universe,
        horizon_type=htype,
        return_basis=basis,
        artifact_id=derived_artifact_id,
        run_id=str(run_id),
        summary_row=summary_row,
        quantile_rows=quantile_rows or [],
    )

    gate_summary = build_metis_gate_summary_from_factor_summary_row(
        summary_row, quantiles=quantile_rows or None, return_basis=basis
    )
    gate_record = promotion_gate_from_validation_summary(
        artifact_id=derived_artifact_id,
        evaluation_run_id=str(run_id),
        summary=gate_summary,
    )
    try:
        gate_dict = gate_record.model_dump()
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        gate_dict = gate_record.dict()  # type: ignore[union-attr]

    verdict, blocking = _gate_verdict_and_blocking_reasons(
        pit_pass=bool(gate_record.pit_pass),
        coverage_pass=bool(gate_record.coverage_pass),
        monotonicity_pass=bool(gate_record.monotonicity_pass),
        gate_reasons=str(gate_record.reasons or ""),
    )

    spearman_raw = summary_row.get("spearman_rank_corr")
    try:
        spearman_abs = abs(float(spearman_raw)) if spearman_raw is not None else None
    except (TypeError, ValueError):
        spearman_abs = None
    gate_metrics: dict[str, Any] = {
        "pit_pass": bool(gate_record.pit_pass),
        "coverage_pass": bool(gate_record.coverage_pass),
        "monotonicity_pass": bool(gate_record.monotonicity_pass),
        "sample_count": int(summary_row.get("sample_count") or 0),
        "valid_factor_count": int(summary_row.get("valid_factor_count") or 0),
        "spearman_abs": spearman_abs,
        "gate_reasons": str(gate_record.reasons or ""),
    }

    current_active = str(entry.get("active_artifact_id") or "")
    current_challengers = list(entry.get("challenger_artifact_ids") or [])
    entry_horizon = str(entry.get("horizon") or "")
    if entry_horizon != horizon:
        blocking_reasons = blocking + [
            f"registry_entry_horizon_mismatch:expected={horizon};actual={entry_horizon}"
        ]
        ev = _build_evaluation_packet(
            evaluation_id=evaluation_id,
            factor_name=factor,
            universe_name=universe,
            horizon_type=htype,
            return_basis=basis,
            validation_run_id=str(run_id),
            validation_pointer=validation_pointer,
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            derived_artifact_id=derived_artifact_id,
            artifact_action="no_change",
            gate_verdict=verdict,
            gate_metrics=gate_metrics,
            blocking_reasons=blocking_reasons,
            outcome="blocked_missing_evidence",
            emitted_proposal_packet_id=None,
            evidence_refs=[
                f"factor_validation_run:{run_id}",
                f"artifact:{derived_artifact_id}",
            ],
            now_iso=now,
        )
        if not dry_run:
            _emit_evaluation(store, ev)
        return {
            "ok": True,
            "evaluation_packet_id": ev.packet_id,
            "outcome": "blocked_missing_evidence",
            "gate_verdict": verdict,
            "artifact_action": "no_change",
            "derived_artifact_id": derived_artifact_id,
            "emitted_proposal_packet_id": None,
            "blocking_reasons": blocking_reasons,
            "dry_run": dry_run,
        }

    existing_artifact = _find_artifact(bundle_dict, artifact_id=derived_artifact_id)
    if derived_artifact_id == current_active:
        artifact_action = "already_active"
    elif derived_artifact_id in current_challengers or existing_artifact is not None:
        artifact_action = "synced_existing"
    else:
        artifact_action = "added_challenger"

    # --- Bundle mutation (if any) + integrity + atomic write. --------------
    mutated = copy.deepcopy(bundle_dict)

    if artifact_action == "added_challenger" and verdict == "promote":
        # Honest rule: only add a brand-new challenger slot when the gate says
        # promote. Otherwise we would pollute the bundle with blocked artifacts.
        arts = list(mutated.get("artifacts") or [])
        arts.append(dict(candidate_artifact))
        mutated["artifacts"] = arts

        entries = list(mutated.get("registry_entries") or [])
        merged_entry = dict(entries[idx])
        challengers = list(merged_entry.get("challenger_artifact_ids") or [])
        challengers = _append_unique(challengers, derived_artifact_id)
        merged_entry["challenger_artifact_ids"] = challengers
        merged_entry["last_evaluator_touch_at_utc"] = now
        entries[idx] = merged_entry
        mutated["registry_entries"] = entries

        # Gate merge lives alongside the artifact so integrity sees a
        # passing gate exists for that id.
        mutated = merge_promotion_gate_into_bundle_dict(mutated, gate_dict)
    elif artifact_action == "synced_existing":
        # Sync validation_pointer for the existing artifact and refresh gate
        # record regardless of verdict (so the gate surface reflects today's
        # metrics). The canonical write path still validates the result.
        try:
            mutated = sync_artifact_validation_pointer_for_factor_run(
                mutated,
                artifact_id=derived_artifact_id,
                evaluation_run_id=str(run_id),
            )
        except ValueError as exc:
            # The artifact id was reported in challenger list but the
            # underlying artifact is missing. Promote to honest block.
            blocking_reasons = blocking + [f"challenger_artifact_missing:{exc}"]
            ev = _build_evaluation_packet(
                evaluation_id=evaluation_id,
                factor_name=factor,
                universe_name=universe,
                horizon_type=htype,
                return_basis=basis,
                validation_run_id=str(run_id),
                validation_pointer=validation_pointer,
                registry_entry_id=registry_entry_id,
                horizon=horizon,
                derived_artifact_id=derived_artifact_id,
                artifact_action="no_change",
                gate_verdict=verdict,
                gate_metrics=gate_metrics,
                blocking_reasons=blocking_reasons,
                outcome="blocked_bundle_integrity",
                emitted_proposal_packet_id=None,
                evidence_refs=[
                    f"factor_validation_run:{run_id}",
                    f"artifact:{derived_artifact_id}",
                ],
                now_iso=now,
            )
            if not dry_run:
                _emit_evaluation(store, ev)
            return {
                "ok": True,
                "evaluation_packet_id": ev.packet_id,
                "outcome": "blocked_bundle_integrity",
                "gate_verdict": verdict,
                "artifact_action": "no_change",
                "derived_artifact_id": derived_artifact_id,
                "emitted_proposal_packet_id": None,
                "blocking_reasons": blocking_reasons,
                "dry_run": dry_run,
            }
        mutated = merge_promotion_gate_into_bundle_dict(mutated, gate_dict)
    elif artifact_action == "already_active":
        # Active artifact: allow pointer sync so the validation_pointer stays
        # fresh, refresh gate record too (it will replace prior gate for that
        # artifact_id without touching active state).
        try:
            mutated = sync_artifact_validation_pointer_for_factor_run(
                mutated,
                artifact_id=derived_artifact_id,
                evaluation_run_id=str(run_id),
            )
        except ValueError:
            # Extremely defensive: active_artifact_id declared but missing
            # from artifacts[] - bundle is malformed upstream. Skip write.
            pass
        mutated = merge_promotion_gate_into_bundle_dict(mutated, gate_dict)
    else:
        # added_challenger but verdict != promote -> no bundle mutation.
        pass

    bundle_changed = mutated is not bundle_dict and (
        mutated.get("artifacts") != bundle_dict.get("artifacts")
        or mutated.get("registry_entries") != bundle_dict.get("registry_entries")
        or mutated.get("promotion_gates") != bundle_dict.get("promotion_gates")
    )

    if bundle_changed:
        integrity_ok, errs = validate_merged_bundle_dict(mutated)
        if not integrity_ok:
            blocking_reasons = blocking + [
                f"bundle_integrity_failed:{errs[:3]}"
            ]
            ev = _build_evaluation_packet(
                evaluation_id=evaluation_id,
                factor_name=factor,
                universe_name=universe,
                horizon_type=htype,
                return_basis=basis,
                validation_run_id=str(run_id),
                validation_pointer=validation_pointer,
                registry_entry_id=registry_entry_id,
                horizon=horizon,
                derived_artifact_id=derived_artifact_id,
                artifact_action="no_change",
                gate_verdict=verdict,
                gate_metrics=gate_metrics,
                blocking_reasons=blocking_reasons,
                outcome="blocked_bundle_integrity",
                emitted_proposal_packet_id=None,
                evidence_refs=[
                    f"factor_validation_run:{run_id}",
                    f"artifact:{derived_artifact_id}",
                ],
                now_iso=now,
            )
            if not dry_run:
                _emit_evaluation(store, ev)
            return {
                "ok": True,
                "evaluation_packet_id": ev.packet_id,
                "outcome": "blocked_bundle_integrity",
                "gate_verdict": verdict,
                "artifact_action": "no_change",
                "derived_artifact_id": derived_artifact_id,
                "emitted_proposal_packet_id": None,
                "blocking_reasons": blocking_reasons,
                "dry_run": dry_run,
            }

        if not dry_run:
            try:
                write_bundle_json_atomic(bundle_path, mutated)
            except Exception as exc:  # pragma: no cover - fs guard
                blocking_reasons = blocking + [f"bundle_write_failed:{exc}"]
                ev = _build_evaluation_packet(
                    evaluation_id=evaluation_id,
                    factor_name=factor,
                    universe_name=universe,
                    horizon_type=htype,
                    return_basis=basis,
                    validation_run_id=str(run_id),
                    validation_pointer=validation_pointer,
                    registry_entry_id=registry_entry_id,
                    horizon=horizon,
                    derived_artifact_id=derived_artifact_id,
                    artifact_action="no_change",
                    gate_verdict=verdict,
                    gate_metrics=gate_metrics,
                    blocking_reasons=blocking_reasons,
                    outcome="blocked_bundle_integrity",
                    emitted_proposal_packet_id=None,
                    evidence_refs=[
                        f"factor_validation_run:{run_id}",
                        f"artifact:{derived_artifact_id}",
                    ],
                    now_iso=now,
                )
                _emit_evaluation(store, ev)
                return {
                    "ok": False,
                    "evaluation_packet_id": ev.packet_id,
                    "outcome": "blocked_bundle_integrity",
                    "gate_verdict": verdict,
                    "artifact_action": "no_change",
                    "derived_artifact_id": derived_artifact_id,
                    "emitted_proposal_packet_id": None,
                    "blocking_reasons": blocking_reasons,
                    "error": f"bundle_write_failed:{exc}",
                    "retryable": False,
                    "dry_run": False,
                }

    # --- Decide outcome + proposal emission. -------------------------------
    emitted_proposal_id: Optional[str] = None
    outcome: str
    if verdict == "promote" and artifact_action == "already_active":
        outcome = "blocked_same_as_active"
    elif verdict == "promote":
        # Recompute challenger sets based on the *mutated* bundle so that if
        # we added a new challenger it reflects in from/to.
        final_entries = list(mutated.get("registry_entries") or [])
        final_entry = dict(final_entries[idx])
        from_challengers = list(final_entry.get("challenger_artifact_ids") or [])
        # "to" moves derived_artifact_id from challengers into active slot.
        to_challengers = [c for c in from_challengers if c != derived_artifact_id]
        to_challengers = _append_unique(to_challengers, current_active)
        evidence_refs = [
            f"factor_validation_run:{run_id}",
            f"promotion_gate:{run_id}:{derived_artifact_id}",
            f"artifact:{derived_artifact_id}",
            f"evaluation:{evaluation_id}",
            validation_pointer,
        ]
        if not dry_run:
            emitted_proposal_id = _build_and_emit_proposal(
                store,
                registry_entry_id=registry_entry_id,
                horizon=horizon,
                from_active=current_active,
                to_active=derived_artifact_id,
                from_challengers=from_challengers,
                to_challengers=to_challengers,
                evidence_refs=evidence_refs,
                now_iso=now,
            )
        else:
            emitted_proposal_id = "dry_run_no_emit"
        outcome = "proposal_emitted"
    else:
        outcome = "blocked_by_gate"

    evidence_refs_for_eval = [
        f"factor_validation_run:{run_id}",
        f"artifact:{derived_artifact_id}",
        validation_pointer,
    ]
    if outcome == "proposal_emitted" and emitted_proposal_id and not dry_run:
        evidence_refs_for_eval.append(f"packet:{emitted_proposal_id}")

    # In dry_run mode, we still build the packet so structural checks run, but
    # we never persist it. The packet validator requires
    # emitted_proposal_packet_id non-empty for outcome=proposal_emitted, so in
    # dry_run we fall back to the "dry_run_no_emit" sentinel.
    packet_emitted_proposal_id: Optional[str]
    if outcome == "proposal_emitted":
        if dry_run:
            packet_emitted_proposal_id = "dry_run_no_emit"
        else:
            packet_emitted_proposal_id = emitted_proposal_id
    else:
        packet_emitted_proposal_id = None

    ev = _build_evaluation_packet(
        evaluation_id=evaluation_id,
        factor_name=factor,
        universe_name=universe,
        horizon_type=htype,
        return_basis=basis,
        validation_run_id=str(run_id),
        validation_pointer=validation_pointer,
        registry_entry_id=registry_entry_id,
        horizon=horizon,
        derived_artifact_id=derived_artifact_id,
        artifact_action=artifact_action,
        gate_verdict=verdict,
        gate_metrics=gate_metrics,
        blocking_reasons=blocking,
        outcome=outcome,
        emitted_proposal_packet_id=packet_emitted_proposal_id,
        evidence_refs=evidence_refs_for_eval,
        now_iso=now,
    )
    if not dry_run:
        _emit_evaluation(store, ev)

    return {
        "ok": True,
        "evaluation_packet_id": ev.packet_id,
        "outcome": outcome,
        "gate_verdict": verdict,
        "artifact_action": artifact_action,
        "derived_artifact_id": derived_artifact_id,
        "emitted_proposal_packet_id": (
            emitted_proposal_id if outcome == "proposal_emitted" and not dry_run else None
        ),
        "blocking_reasons": list(blocking),
        "dry_run": dry_run,
        "dry_run_preview": (
            {
                "would_emit_proposal": outcome == "proposal_emitted",
                "mutated_artifacts": len(mutated.get("artifacts") or [])
                != len(bundle_dict.get("artifacts") or []),
                "mutated_registry_entries": len(mutated.get("registry_entries") or [])
                != len(bundle_dict.get("registry_entries") or []),
            }
            if dry_run
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Walker: evaluate all registry entries against a supplied "spec list".
# ---------------------------------------------------------------------------


_MUTATING_ACTIONS = frozenset(
    {
        "added_challenger",
        "promoted",
        "promoted_active",
        "bundle_mutated",
    }
)


def evaluate_registry_entries(
    *,
    store: HarnessStoreProtocol,
    bundle_path: Path,
    specs: list[dict[str, Any]],
    supabase_client: Optional[Any] = None,
    now_iso: Optional[str] = None,
    fetch_validation_summary: Optional[FetchValidationSummary] = None,
    fetch_quantiles: Optional[FetchQuantiles] = None,
    dry_run: bool = False,
    reload_between_specs: bool = False,
) -> list[dict[str, Any]]:
    """Evaluate every spec against a single shared bundle snapshot.

    AGH v1 Patch 8 C2b — ``reload_between_specs`` controls the reload policy:

    * ``False`` (default, Patch 8): load the bundle **once** at the start.
      After each spec we only reload if the previous evaluation actually
      mutated the bundle (``artifact_action`` in ``_MUTATING_ACTIONS``) so
      subsequent specs see the fresh composed state. For a typical
      ``no_change`` / ``already_active`` sweep across ~25 registry entries
      this removes ~24 disk reads without changing the semantic guarantee
      that mutations stack deterministically.
    * ``True`` (legacy): reload every iteration (pre-Patch 8 behaviour).
      Used by tests pinning the old contract and for explicit
      defensive-mode runs.

    ``specs`` is a list of dicts with keys ``registry_entry_id, horizon,
    factor_name, universe_name, horizon_type, return_basis``.
    """

    now = str(now_iso or _now_iso())
    results: list[dict[str, Any]] = []
    bundle_dict = load_bundle_json(bundle_path) if specs else None
    bundle_reloads = 1 if specs else 0
    last_mutated = False
    for spec in specs:
        if reload_between_specs or last_mutated:
            bundle_dict = load_bundle_json(bundle_path)
            bundle_reloads += 1
            last_mutated = False
        res = evaluate_validation_for_promotion(
            store=store,
            bundle_path=bundle_path,
            bundle_dict=bundle_dict,
            registry_entry_id=str(spec["registry_entry_id"]),
            horizon=str(spec["horizon"]),
            factor_name=str(spec["factor_name"]),
            universe_name=str(spec["universe_name"]),
            horizon_type=str(spec["horizon_type"]),
            return_basis=str(spec["return_basis"]),
            supabase_client=supabase_client,
            now_iso=now,
            fetch_validation_summary=fetch_validation_summary,
            fetch_quantiles=fetch_quantiles,
            dry_run=dry_run,
        )
        res["spec"] = dict(spec)
        results.append(res)
        # AGH v1 Patch 8 C2b — detect mutation so the next iteration reloads.
        if not dry_run and str(res.get("artifact_action") or "") in _MUTATING_ACTIONS:
            last_mutated = True
    # Stash a single aggregate marker on the last result so runbooks /
    # evidence scripts can verify single-reload mode without parsing stderr.
    if results:
        results[-1]["_bundle_reloads_total"] = bundle_reloads
        results[-1]["_reload_policy"] = (
            "legacy_reload_every_spec" if reload_between_specs else "single_reload_with_mutation_reload"
        )
    return results


# ---------------------------------------------------------------------------
# Cadence hook: governance_scan tick. Bootstrapped by ``runtime.build_layer_cadences``.
# ---------------------------------------------------------------------------


# Optional external provider: a callable (store, now_iso) -> list[spec dict].
# If None, the cadence tick is a honest skip (reports ``no_provider``). Tests
# and runbooks set this via ``set_governance_scan_spec_provider``.
GovernanceScanSpecProvider = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
_GOVERNANCE_SCAN_SPEC_PROVIDER: Optional[GovernanceScanSpecProvider] = None

# Optional supabase client factory for the cadence run. If None, walker runs
# with ``supabase_client=None`` (honest skip paths will dominate unless tests
# supply fetchers explicitly).
SupabaseClientFactory = Callable[[], Any]
_GOVERNANCE_SCAN_CLIENT_FACTORY: Optional[SupabaseClientFactory] = None


def set_governance_scan_spec_provider(
    fn: Optional[GovernanceScanSpecProvider],
) -> None:
    global _GOVERNANCE_SCAN_SPEC_PROVIDER
    _GOVERNANCE_SCAN_SPEC_PROVIDER = fn


def set_governance_scan_client_factory(
    fn: Optional[SupabaseClientFactory],
) -> None:
    global _GOVERNANCE_SCAN_CLIENT_FACTORY
    _GOVERNANCE_SCAN_CLIENT_FACTORY = fn


def propose_governance_scan_cadence(
    store: HarnessStoreProtocol, now_iso: str
) -> dict[str, Any]:
    """``LayerCadenceSpec`` propose_fn for ``governance_scan``.

    Walks the provider-supplied spec list (if any) and evaluates each slot.
    Returns a summary dict consumed by ``run_one_tick``.
    """

    provider = _GOVERNANCE_SCAN_SPEC_PROVIDER
    if provider is None:
        return {"skipped": True, "reason": "no_governance_scan_spec_provider"}
    specs: list[dict[str, Any]] = []
    try:
        specs = list(provider(store, now_iso) or [])
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan provider failed: %s", exc)
        return {"skipped": True, "reason": f"provider_error:{exc}"}
    if not specs:
        return {"scans": 0, "reason": "empty_spec_list"}

    repo_root = _repo_root_from_env()
    bundle_path = brain_bundle_path(repo_root)

    client: Any = None
    factory = _GOVERNANCE_SCAN_CLIENT_FACTORY
    if factory is not None:
        try:
            client = factory()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("governance_scan client factory failed: %s", exc)
            client = None

    try:
        results = evaluate_registry_entries(
            store=store,
            bundle_path=bundle_path,
            specs=specs,
            supabase_client=client,
            now_iso=now_iso,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan evaluation failed: %s", exc)
        return {"skipped": True, "reason": f"evaluation_error:{exc}"}

    summary_counts: dict[str, int] = {}
    emitted_proposal_ids: list[str] = []
    for r in results:
        outcome = str(r.get("outcome") or "unknown")
        summary_counts[outcome] = summary_counts.get(outcome, 0) + 1
        pid = r.get("emitted_proposal_packet_id")
        if pid and str(pid) != "dry_run_no_emit":
            emitted_proposal_ids.append(str(pid))

    return {
        "scans": len(results),
        "by_outcome": summary_counts,
        "emitted_proposal_packet_ids": emitted_proposal_ids,
    }
