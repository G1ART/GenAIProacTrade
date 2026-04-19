"""Layer 4 - Registry Patch Executor (AGH v1 Patch 2 + Patch 3).

Consumes jobs from ``registry_apply_queue`` and, for an operator-approved
``RegistryUpdateProposalV1``, performs a deterministic atomic write of the
brain bundle. Supports two governed apply targets:

    * ``horizon_provenance``              (Patch 2) —
        rewrites ``bundle.horizon_provenance[horizon].source``.
    * ``registry_entry_artifact_promotion`` (Patch 3) —
        swaps ``registry_entries[...].active_artifact_id`` with a challenger,
        refreshes ``spectrum_rows_by_horizon[horizon]`` deterministically,
        and records a FIFO of recent governed applies onto the bundle so
        Today can surface horizon-scoped badges without a new worker.

Invariants (Work-order METIS_Patch_{2,3} §3 / §5.B / §6.2):
    * The worker NEVER writes raw SQL into any registry table. The canonical
      registry write path is the brain-bundle JSON + ``validate_merged_bundle_dict``
      + atomic write chain from ``metis_brain.bundle_promotion_merge_v0``.
    * ``from_state`` / ``from_active_artifact_id`` / ``from_challenger_artifact_ids``
      are verified against the current bundle; mismatches land as
      ``conflict_skip`` (outcome recorded, proposal deferred) instead of a
      silent apply.
    * ``validate_merged_bundle_dict`` must pass before the atomic write.
    * Success emits a ``RegistryPatchAppliedPacketV1`` with before/after
      snapshots so replay can reconstruct the transition.  The
      ``registry_entry_artifact_promotion`` path additionally emits a
      ``SpectrumRefreshRecordV1`` citing the applied packet so the refresh
      outcome (recomputed vs. carry-over) is first-class audit data.
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

from agentic_harness.agents.layer4_spectrum_refresh_v1 import (
    refresh_spectrum_rows_for_horizon,
)
from agentic_harness.contracts.packets_v1 import (
    HORIZON_STATE_VALUES,
    REGISTRY_BUNDLE_HORIZONS,
    REGISTRY_PROPOSAL_TARGETS,
    RegistryPatchAppliedPacketV1,
    SpectrumRefreshRecordV1,
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

# Patch 3: bounded FIFO cap for bundle.recent_governed_applies. Oldest entries
# are evicted once the list exceeds this size. Keeping it small ensures Today
# reads stay cheap and the bundle JSON does not grow unboundedly over time.
RECENT_GOVERNED_APPLIES_CAP = 20


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _repo_root_from_env() -> Path:
    override = (os.environ.get("METIS_REPO_ROOT") or "").strip()
    if override:
        return Path(override)
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
    target: str,
    horizon: str,
    payload_extras: dict[str, Any],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    outcome: str,
    bundle_path: str,
    now_iso: str,
    extra_blocking_reasons: Optional[list[str]] = None,
    confidence_override: Optional[float] = None,
) -> str:
    pid = deterministic_packet_id(
        packet_type="RegistryPatchAppliedPacketV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "proposal_packet_id": proposal_id,
            "horizon": horizon,
            "target": target,
            "outcome": outcome,
        },
        salt=now_iso,
    )
    payload: dict[str, Any] = {
        "outcome": outcome,
        "target": target,
        "horizon": horizon,
        "cited_proposal_packet_id": proposal_id,
        "cited_decision_packet_id": decision_id,
        "applied_at_utc": now_iso,
        "bundle_path": bundle_path,
        "before_snapshot": before_snapshot,
        "after_snapshot": after_snapshot,
    }
    payload.update(payload_extras)
    pkt = RegistryPatchAppliedPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryPatchAppliedPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "registry_patch_executor",
            "target_scope": {
                "proposal_packet_id": proposal_id,
                "horizon": horizon,
                "target": target,
            },
            "provenance_refs": [
                f"packet:{proposal_id}",
                f"packet:{decision_id}",
            ],
            "confidence": (
                confidence_override
                if confidence_override is not None
                else (1.0 if outcome == "applied" else 0.5)
            ),
            "blocking_reasons": list(extra_blocking_reasons or []),
            "status": "done",
            "payload": payload,
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pkt.packet_id


def _emit_spectrum_refresh_record(
    store: HarnessStoreProtocol,
    *,
    refresh_result: dict[str, Any],
    proposal_id: str,
    decision_id: str,
    applied_packet_id: str,
    now_iso: str,
) -> str:
    pid = deterministic_packet_id(
        packet_type="SpectrumRefreshRecordV1",
        created_by_agent="registry_patch_executor",
        target_scope={
            "applied_packet_id": applied_packet_id,
            "horizon": refresh_result.get("horizon"),
            "registry_entry_id": refresh_result.get("registry_entry_id"),
        },
        salt=now_iso,
    )
    payload = dict(refresh_result)
    payload["cited_applied_packet_id"] = applied_packet_id
    payload["cited_proposal_packet_id"] = proposal_id
    payload["cited_decision_packet_id"] = decision_id
    pkt = SpectrumRefreshRecordV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "SpectrumRefreshRecordV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "registry_patch_executor",
            "target_scope": {
                "applied_packet_id": applied_packet_id,
                "horizon": refresh_result.get("horizon"),
                "registry_entry_id": refresh_result.get("registry_entry_id"),
            },
            "provenance_refs": [
                f"packet:{applied_packet_id}",
                f"packet:{proposal_id}",
                f"packet:{decision_id}",
            ],
            "confidence": (
                1.0 if refresh_result.get("outcome") == "recomputed" else 0.5
            ),
            "blocking_reasons": list(refresh_result.get("blocking_reasons") or []),
            "status": "done",
            "payload": payload,
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pkt.packet_id


def _find_registry_entry(
    bundle: dict[str, Any], *, registry_entry_id: str
) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    entries = bundle.get("registry_entries") or []
    for i, e in enumerate(entries):
        if str((e or {}).get("registry_entry_id") or "") == registry_entry_id:
            return i, dict(e)
    return None, None


def _append_recent_governed_apply(
    bundle: dict[str, Any], entry: dict[str, Any]
) -> list[dict[str, Any]]:
    tail = list(bundle.get("recent_governed_applies") or [])
    tail.append(dict(entry))
    if len(tail) > RECENT_GOVERNED_APPLIES_CAP:
        tail = tail[-RECENT_GOVERNED_APPLIES_CAP:]
    bundle["recent_governed_applies"] = tail
    return tail


def _apply_horizon_provenance(
    store: HarnessStoreProtocol,
    *,
    bundle: dict[str, Any],
    bundle_path: Path,
    proposal_id: str,
    decision_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    horizon = str(payload.get("horizon") or "")
    from_state = str(payload.get("from_state") or "")
    to_state = str(payload.get("to_state") or "")
    if (
        not horizon
        or from_state not in HORIZON_STATE_VALUES
        or to_state not in HORIZON_STATE_VALUES
    ):
        return {
            "ok": False,
            "error": (
                "invalid_proposal_payload:"
                f"horizon={horizon!r} from_state={from_state!r} to_state={to_state!r}"
            ),
            "retryable": False,
        }

    horizon_provenance = dict(bundle.get("horizon_provenance") or {})
    prov_entry = horizon_provenance.get(horizon)
    if not isinstance(prov_entry, dict):
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            target="horizon_provenance",
            horizon=horizon,
            payload_extras={"from_state": from_state, "to_state": to_state},
            before_snapshot={
                "horizon_provenance": {horizon: {"missing": True}}
            },
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
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            target="horizon_provenance",
            horizon=horizon,
            payload_extras={"from_state": from_state, "to_state": to_state},
            before_snapshot={
                "horizon_provenance": {horizon: before_snapshot}
            },
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
    except Exception as exc:
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
        target="horizon_provenance",
        horizon=horizon,
        payload_extras={"from_state": from_state, "to_state": to_state},
        before_snapshot={"horizon_provenance": {horizon: before_snapshot}},
        after_snapshot={"horizon_provenance": {horizon: after_snapshot}},
        outcome="applied",
        bundle_path=str(bundle_path),
        now_iso=now_iso,
    )
    store.set_packet_status(proposal_id, "applied")
    log.info(
        "registry_patch_executor horizon_provenance applied proposal=%s horizon=%s %s->%s",
        proposal_id,
        horizon,
        from_state,
        to_state,
    )
    return {
        "ok": True,
        "outcome": "applied",
        "applied_packet_id": applied_id,
        "before": before_snapshot,
        "after": after_snapshot,
    }


def _apply_registry_entry_artifact_promotion(
    store: HarnessStoreProtocol,
    *,
    bundle: dict[str, Any],
    bundle_path: Path,
    proposal_id: str,
    decision_id: str,
    payload: dict[str, Any],
    supabase_client: Optional[Any] = None,
) -> dict[str, Any]:
    registry_entry_id = str(payload.get("registry_entry_id") or "")
    horizon = str(payload.get("horizon") or "")
    from_active = str(payload.get("from_active_artifact_id") or "")
    to_active = str(payload.get("to_active_artifact_id") or "")
    from_challengers = list(payload.get("from_challenger_artifact_ids") or [])
    to_challengers = list(payload.get("to_challenger_artifact_ids") or [])

    if (
        not registry_entry_id
        or horizon not in REGISTRY_BUNDLE_HORIZONS
        or not from_active
        or not to_active
        or from_active == to_active
    ):
        return {
            "ok": False,
            "error": (
                "invalid_artifact_promotion_payload:"
                f"registry_entry_id={registry_entry_id!r} horizon={horizon!r} "
                f"from={from_active!r} to={to_active!r}"
            ),
            "retryable": False,
        }

    idx, entry = _find_registry_entry(bundle, registry_entry_id=registry_entry_id)
    if entry is None:
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            target="registry_entry_artifact_promotion",
            horizon=horizon,
            payload_extras={"registry_entry_id": registry_entry_id},
            before_snapshot={"registry_entry": {"missing": True}},
            after_snapshot={},
            outcome="conflict_skip",
            bundle_path=str(bundle_path),
            now_iso=_now_iso(),
            extra_blocking_reasons=[
                f"registry_entry_missing:{registry_entry_id}"
            ],
        )
        store.set_packet_status(proposal_id, "deferred")
        return {
            "ok": True,
            "outcome": "conflict_skip",
            "applied_packet_id": applied_id,
            "reason": f"registry_entry_missing:{registry_entry_id}",
        }

    current_active = str(entry.get("active_artifact_id") or "")
    current_challengers = list(entry.get("challenger_artifact_ids") or [])
    mismatch_reasons: list[str] = []
    if current_active != from_active:
        mismatch_reasons.append(
            f"active_mismatch:expected={from_active} actual={current_active}"
        )
    if set(current_challengers) != set(from_challengers):
        mismatch_reasons.append(
            "challenger_mismatch:"
            f"expected={sorted(from_challengers)} actual={sorted(current_challengers)}"
        )
    if str(entry.get("horizon") or "") != horizon:
        mismatch_reasons.append(
            f"horizon_mismatch:expected={horizon} actual={entry.get('horizon')!r}"
        )
    if mismatch_reasons:
        applied_id = _emit_applied_packet(
            store,
            proposal_id=proposal_id,
            decision_id=decision_id,
            target="registry_entry_artifact_promotion",
            horizon=horizon,
            payload_extras={"registry_entry_id": registry_entry_id},
            before_snapshot={"registry_entry": copy.deepcopy(entry)},
            after_snapshot={},
            outcome="conflict_skip",
            bundle_path=str(bundle_path),
            now_iso=_now_iso(),
            extra_blocking_reasons=mismatch_reasons,
        )
        store.set_packet_status(proposal_id, "deferred")
        return {
            "ok": True,
            "outcome": "conflict_skip",
            "applied_packet_id": applied_id,
            "reason": mismatch_reasons[0],
        }

    artifacts_by_id = {
        str((a or {}).get("artifact_id") or ""): a
        for a in (bundle.get("artifacts") or [])
    }
    if to_active not in artifacts_by_id:
        return {
            "ok": False,
            "error": f"to_active_artifact_missing:{to_active}",
            "retryable": False,
        }
    to_art = artifacts_by_id[to_active]
    if str(to_art.get("horizon") or "") != horizon:
        return {
            "ok": False,
            "error": (
                f"to_active_artifact_horizon_mismatch:"
                f"expected={horizon} actual={to_art.get('horizon')!r}"
            ),
            "retryable": False,
        }

    for cid in to_challengers:
        if cid == to_active:
            return {
                "ok": False,
                "error": (
                    "to_challenger_overlaps_to_active:"
                    f"challenger={cid} active={to_active}"
                ),
                "retryable": False,
            }
        if cid not in artifacts_by_id:
            return {
                "ok": False,
                "error": f"to_challenger_artifact_missing:{cid}",
                "retryable": False,
            }

    now_iso = _now_iso()
    mutated = copy.deepcopy(bundle)
    before_snapshot_entry = copy.deepcopy(entry)

    entries = list(mutated.get("registry_entries") or [])
    mutated_entry = dict(entries[idx])
    mutated_entry["active_artifact_id"] = to_active
    mutated_entry["challenger_artifact_ids"] = list(to_challengers)
    mutated_entry["last_governed_update_at_utc"] = now_iso
    mutated_entry["last_governed_proposal_packet_id"] = proposal_id
    mutated_entry["last_governed_decision_packet_id"] = decision_id
    entries[idx] = mutated_entry
    mutated["registry_entries"] = entries

    refresh_result = refresh_spectrum_rows_for_horizon(
        mutated,
        horizon=horizon,
        new_active_artifact_id=to_active,
        registry_entry_id=registry_entry_id,
        now_iso=now_iso,
        bundle_path=str(bundle_path),
        cited_proposal_packet_id=proposal_id,
        cited_decision_packet_id=decision_id,
        supabase_client=supabase_client,
    )

    recent_entry = {
        "target": "registry_entry_artifact_promotion",
        "horizon": horizon,
        "registry_entry_id": registry_entry_id,
        "proposal_packet_id": proposal_id,
        "decision_packet_id": decision_id,
        "from_active_artifact_id": from_active,
        "to_active_artifact_id": to_active,
        "applied_at_utc": now_iso,
        "spectrum_refresh_outcome": refresh_result.get("outcome"),
        "spectrum_refresh_needs_db_rebuild": bool(
            refresh_result.get("needs_db_rebuild")
        ),
    }
    _append_recent_governed_apply(mutated, recent_entry)

    integrity_ok, errs = validate_merged_bundle_dict(mutated)
    if not integrity_ok:
        return {
            "ok": False,
            "error": f"bundle_integrity_failed:{errs[:3]}",
            "retryable": False,
        }

    try:
        write_bundle_json_atomic(bundle_path, mutated)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"bundle_write_failed:{exc}",
            "retryable": False,
        }

    after_entry_snapshot = copy.deepcopy(mutated_entry)
    applied_id = _emit_applied_packet(
        store,
        proposal_id=proposal_id,
        decision_id=decision_id,
        target="registry_entry_artifact_promotion",
        horizon=horizon,
        payload_extras={
            "registry_entry_id": registry_entry_id,
            "from_active_artifact_id": from_active,
            "to_active_artifact_id": to_active,
            "from_challenger_artifact_ids": sorted(from_challengers),
            "to_challenger_artifact_ids": sorted(to_challengers),
            "spectrum_refresh_outcome": refresh_result.get("outcome"),
            "spectrum_refresh_needs_db_rebuild": bool(
                refresh_result.get("needs_db_rebuild")
            ),
        },
        before_snapshot={"registry_entry": before_snapshot_entry},
        after_snapshot={
            "registry_entry": after_entry_snapshot,
            "recent_governed_applies_tail": recent_entry,
        },
        outcome="applied",
        bundle_path=str(bundle_path),
        now_iso=now_iso,
    )

    refresh_id = _emit_spectrum_refresh_record(
        store,
        refresh_result=refresh_result,
        proposal_id=proposal_id,
        decision_id=decision_id,
        applied_packet_id=applied_id,
        now_iso=now_iso,
    )

    store.set_packet_status(proposal_id, "applied")
    log.info(
        "registry_patch_executor artifact_promotion applied proposal=%s "
        "entry=%s horizon=%s %s->%s refresh=%s",
        proposal_id,
        registry_entry_id,
        horizon,
        from_active,
        to_active,
        refresh_result.get("outcome"),
    )
    return {
        "ok": True,
        "outcome": "applied",
        "applied_packet_id": applied_id,
        "refresh_record_id": refresh_id,
        "refresh_outcome": refresh_result.get("outcome"),
        "before": before_snapshot_entry,
        "after": after_entry_snapshot,
    }


def registry_patch_executor(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Worker for ``registry_apply_queue``.

    Return shape follows the scheduler / worker contract:

    * Success (governed write committed):
      ``{ok: True, outcome: 'applied', applied_packet_id, before, after[,
      refresh_record_id, refresh_outcome]}``
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
        return {
            "ok": True,
            "skipped": True,
            "reason": f"proposal_not_escalated:{status}",
        }

    decision = _find_approve_decision(store, proposal_id)
    if decision is None:
        return {
            "ok": False,
            "error": f"no_approve_decision_for_proposal:{proposal_id}",
            "retryable": False,
        }
    decision_id = str(decision.get("packet_id") or "")

    payload = pkt.get("payload") or {}
    target = str(payload.get("target") or "")
    if target not in REGISTRY_PROPOSAL_TARGETS:
        return {
            "ok": False,
            "error": (
                f"unsupported_proposal_target:{target!r} "
                f"(allowed={REGISTRY_PROPOSAL_TARGETS})"
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
    except Exception as exc:
        return {
            "ok": False,
            "error": f"bundle_load_failed:{exc}",
            "retryable": False,
        }

    if target == "horizon_provenance":
        return _apply_horizon_provenance(
            store,
            bundle=bundle,
            bundle_path=bundle_path,
            proposal_id=proposal_id,
            decision_id=decision_id,
            payload=payload,
        )
    # target == "registry_entry_artifact_promotion"
    return _apply_registry_entry_artifact_promotion(
        store,
        bundle=bundle,
        bundle_path=bundle_path,
        proposal_id=proposal_id,
        decision_id=decision_id,
        payload=payload,
    )
