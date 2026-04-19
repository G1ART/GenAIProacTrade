"""Layer 4 - Registry Patch Executor (AGH v1 Patch 2).

Consumes jobs from ``registry_apply_queue`` and, for an operator-approved
``RegistryUpdateProposalV1``, performs a deterministic atomic write of the
brain bundle's ``horizon_provenance[horizon].source`` field.

Invariants (Work-order METIS_Patch_2 §3 / §6.2):
    * The worker NEVER writes raw SQL into any registry table. The canonical
      registry write path is the brain-bundle JSON + ``validate_merged_bundle_dict``
      + ``write_bundle_json`` chain from ``metis_brain.bundle_promotion_merge_v0``.
    * ``from_state`` is verified against the current bundle; mismatches land as
      ``conflict_skip`` (outcome recorded, proposal deferred) instead of a
      silent apply.
    * ``validate_merged_bundle_dict`` must pass before the atomic write.
    * Success emits a ``RegistryPatchAppliedPacketV1`` with before/after
      snapshots so replay can reconstruct the transition.
    * The proposal packet's status moves to ``applied`` only after the write
      succeeds; conflict_skip moves it to ``deferred``; failures mark the
      apply job for DLQ (retryable=False) without mutating the bundle.
    * Idempotent: a proposal whose status is not ``escalated`` is skipped.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any, Optional

from agentic_harness.contracts.packets_v1 import (
    HORIZON_STATE_VALUES,
    RegistryPatchAppliedPacketV1,
    deterministic_packet_id,
)
from agentic_harness.store.protocol import HarnessStoreProtocol
from metis_brain.bundle import brain_bundle_path
from metis_brain.bundle_promotion_merge_v0 import (
    load_bundle_json,
    validate_merged_bundle_dict,
    write_bundle_json_atomic,
)


log = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _repo_root_from_env() -> Path:
    override = (os.environ.get("METIS_REPO_ROOT") or "").strip()
    if override:
        return Path(override)
    # Walk up from this file to the repo root (four levels above src/).
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "mvp").exists():
            return parent
    return here.parents[3]


def _find_approve_decision(
    store: HarnessStoreProtocol, proposal_id: str
) -> Optional[dict[str, Any]]:
    rows = store.list_packets(
        packet_type="RegistryDecisionPacketV1", limit=500
    )
    for r in rows:
        payload = r.get("payload") or {}
        if str(payload.get("cited_proposal_packet_id") or "") != proposal_id:
            continue
        if str(payload.get("action") or "") == "approve":
            return r
    return None


def _emit_applied_packet(
    store: HarnessStoreProtocol,
    *,
    proposal_id: str,
    decision_id: str,
    horizon: str,
    from_state: str,
    to_state: str,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    outcome: str,
    bundle_path: str,
    now_iso: str,
    extra_blocking_reasons: Optional[list[str]] = None,
) -> str:
    pid = deterministic_packet_id(
        packet_type="RegistryPatchAppliedPacketV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "proposal_packet_id": proposal_id,
            "horizon": horizon,
            "outcome": outcome,
        },
        salt=now_iso,
    )
    pkt = RegistryPatchAppliedPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryPatchAppliedPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "registry_patch_executor",
            "target_scope": {
                "proposal_packet_id": proposal_id,
                "horizon": horizon,
                "target": "horizon_provenance",
            },
            "provenance_refs": [
                f"packet:{proposal_id}",
                f"packet:{decision_id}",
            ],
            "confidence": 1.0 if outcome == "applied" else 0.5,
            "blocking_reasons": list(extra_blocking_reasons or []),
            "status": "done",
            "payload": {
                "outcome": outcome,
                "target": "horizon_provenance",
                "horizon": horizon,
                "from_state": from_state,
                "to_state": to_state,
                "cited_proposal_packet_id": proposal_id,
                "cited_decision_packet_id": decision_id,
                "applied_at_utc": now_iso,
                "bundle_path": bundle_path,
                "before_snapshot": {"horizon_provenance": {horizon: before_snapshot}},
                "after_snapshot": (
                    {"horizon_provenance": {horizon: after_snapshot}}
                    if after_snapshot
                    else {}
                ),
            },
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pkt.packet_id


def registry_patch_executor(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Worker for ``registry_apply_queue``.

    Return shape follows the scheduler / worker contract:

    * Success (governed write committed):
      ``{ok: True, outcome: 'applied', applied_packet_id, before, after}``
    * Success (conflict_skip, no write):
      ``{ok: True, outcome: 'conflict_skip', applied_packet_id, reason}``
    * Idempotent skip (proposal not in escalated):
      ``{ok: True, skipped: True, reason}``
    * Failure (retryable=False -> DLQ):
      ``{ok: False, error, retryable: False}``
    """

    proposal_id = str(job_row.get("packet_id") or "")
    if not proposal_id:
        return {"ok": False, "error": "job_row.packet_id missing", "retryable": False}

    pkt = store.get_packet(proposal_id)
    if pkt is None:
        return {
            "ok": False,
            "error": f"proposal_missing:{proposal_id}",
            "retryable": False,
        }
    if str(pkt.get("packet_type") or "") != "RegistryUpdateProposalV1":
        return {
            "ok": False,
            "error": (
                f"wrong_packet_type:{pkt.get('packet_type')!r} for {proposal_id}"
            ),
            "retryable": False,
        }

    status = str(pkt.get("status") or "")
    if status != "escalated":
        # Idempotent: already applied / rejected / deferred / etc.
        return {
            "ok": True,
            "skipped": True,
            "reason": f"proposal_not_escalated:{status}",
        }

    decision = _find_approve_decision(store, proposal_id)
    if decision is None:
        # An apply job without an approve decision is a contract break.
        return {
            "ok": False,
            "error": f"no_approve_decision_for_proposal:{proposal_id}",
            "retryable": False,
        }
    decision_id = str(decision.get("packet_id") or "")

    payload = pkt.get("payload") or {}
    target = str(payload.get("target") or "")
    if target != "horizon_provenance":
        return {
            "ok": False,
            "error": (
                f"unsupported_proposal_target:{target!r} (only horizon_provenance)"
            ),
            "retryable": False,
        }
    horizon = str(payload.get("horizon") or "")
    from_state = str(payload.get("from_state") or "")
    to_state = str(payload.get("to_state") or "")
    if not horizon or from_state not in HORIZON_STATE_VALUES or to_state not in HORIZON_STATE_VALUES:
        return {
            "ok": False,
            "error": (
                "invalid_proposal_payload:"
                f"horizon={horizon!r} from_state={from_state!r} to_state={to_state!r}"
            ),
            "retryable": False,
        }

    repo_root = _repo_root_from_env()
    bundle_path = brain_bundle_path(repo_root)
    try:
        bundle = load_bundle_json(bundle_path)
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"bundle_missing:{bundle_path}",
            "retryable": False,
        }
    except Exception as exc:  # defensive: corrupt JSON
        return {
            "ok": False,
            "error": f"bundle_load_failed:{exc}",
            "retryable": False,
        }

    horizon_provenance = dict(bundle.get("horizon_provenance") or {})
    prov_entry = horizon_provenance.get(horizon)
    if not isinstance(prov_entry, dict):
        # Honest fallback: proposal targets a horizon the bundle does not
        # know about. Record conflict_skip so surface stays honest.
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            horizon=horizon,
            from_state=from_state,
            to_state=to_state,
            before_snapshot={"missing": True},
            after_snapshot={},
            outcome="conflict_skip",
            bundle_path=str(bundle_path),
            now_iso=_now_iso(),
            extra_blocking_reasons=[
                f"horizon_provenance_missing_horizon:{horizon}"
            ],
        )
        store.set_packet_status(proposal_id, "deferred")
        return {
            "ok": True,
            "outcome": "conflict_skip",
            "applied_packet_id": applied_id,
            "reason": f"horizon_missing:{horizon}",
        }

    before_snapshot = copy.deepcopy(prov_entry)
    current_source = str(prov_entry.get("source") or "")
    if current_source != from_state:
        # Conflict: the current bundle state has moved since the proposal
        # was created. Do not silently overwrite.
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            horizon=horizon,
            from_state=from_state,
            to_state=to_state,
            before_snapshot=before_snapshot,
            after_snapshot={},
            outcome="conflict_skip",
            bundle_path=str(bundle_path),
            now_iso=_now_iso(),
            extra_blocking_reasons=[
                f"from_state_mismatch:expected={from_state} actual={current_source}"
            ],
        )
        store.set_packet_status(proposal_id, "deferred")
        return {
            "ok": True,
            "outcome": "conflict_skip",
            "applied_packet_id": applied_id,
            "reason": (
                f"from_state_mismatch:expected={from_state} actual={current_source}"
            ),
        }

    # Apply the governed write in-memory first.
    now_iso = _now_iso()
    mutated = copy.deepcopy(bundle)
    mutated_prov = dict(mutated.get("horizon_provenance") or {})
    mutated_entry = dict(mutated_prov.get(horizon) or {})
    mutated_entry["source"] = to_state
    mutated_entry["last_governed_update_at_utc"] = now_iso
    mutated_entry["last_governed_proposal_packet_id"] = proposal_id
    mutated_entry["last_governed_decision_packet_id"] = decision_id
    mutated_prov[horizon] = mutated_entry
    mutated["horizon_provenance"] = mutated_prov

    integrity_ok, errs = validate_merged_bundle_dict(mutated)
    if not integrity_ok:
        return {
            "ok": False,
            "error": f"bundle_integrity_failed:{errs[:3]}",
            "retryable": False,
        }

    try:
        write_bundle_json_atomic(bundle_path, mutated)
    except Exception as exc:  # IO failure
        return {
            "ok": False,
            "error": f"bundle_write_failed:{exc}",
            "retryable": False,
        }

    after_snapshot = copy.deepcopy(mutated_entry)
    applied_id = _emit_applied_packet(
        store,
        proposal_id=proposal_id,
        decision_id=decision_id,
        horizon=horizon,
        from_state=from_state,
        to_state=to_state,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        outcome="applied",
        bundle_path=str(bundle_path),
        now_iso=now_iso,
    )
    store.set_packet_status(proposal_id, "applied")
    log.info(
        "registry_patch_executor applied proposal=%s horizon=%s %s->%s bundle=%s",
        proposal_id,
        horizon,
        from_state,
        to_state,
        bundle_path,
    )
    return {
        "ok": True,
        "outcome": "applied",
        "applied_packet_id": applied_id,
        "before": before_snapshot,
        "after": after_snapshot,
    }
