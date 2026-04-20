"""Layer 3 - Sandbox Executor v1 (AGH v1 Patch 5).

Consumes jobs from ``sandbox_queue`` and produces a single
``SandboxResultPacketV1`` per ``SandboxRequestPacketV1``. Patch 5 supports
exactly one ``sandbox_kind``: ``validation_rerun`` (re-run the
registry-entry's canonical ``factor_validation`` spec and record the
produced ``factor_validation_run_id`` on the result packet). Additional
kinds (``evidence_refresh`` / ``residual_review`` / ``replay_comparison``)
are reserved for a follow-up patch and are surfaced honestly via the
``rejected_kind_not_allowed`` outcome.

Invariants (Workorder METIS_Patch_5 §3 / §5.C):

* **No active registry mutation.** The worker MUST NOT write to the brain
  bundle, the registry_entries section, or any promotion artifact. The
  sandbox path is a bounded research loop and operator-gated promotion
  continues to ride Patch 2/3/4 rails.
* **Idempotent.** A second job for the same request_id is short-circuited
  on the existing ``SandboxResultPacketV1`` if one already cites it.
* **Runner injection.** The production ``validation_rerun`` runner is
  injected via ``set_sandbox_validation_rerun_runner`` (Supabase client +
  ``run_factor_validation_research``). Tests install a deterministic stub.
  With no runner and no client factory, jobs land as
  ``blocked_insufficient_inputs`` rather than pretending to run.
* **Audit-first.** Every outcome is recorded as a typed packet; the
  active-registry scan (Today / Replay) then picks the result up via
  ``cited_request_packet_id`` joins.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    SANDBOX_KINDS,
    SandboxRequestPacketV1,
    SandboxResultPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Injection hooks
# ----------------------------------------------------------------------------
# Keeping these module-level singletons (not class instances) mirrors the
# pattern used by ``layer4_promotion_evaluator_v1`` so the runtime bootstrap
# logic in ``agentic_harness.runtime`` has a single idempotent install path.

_VALIDATION_RERUN_RUNNER: Optional[
    Callable[[dict[str, Any], Any], dict[str, Any]]
] = None

_SANDBOX_CLIENT_FACTORY: Optional[Callable[[], Any]] = None


def set_sandbox_validation_rerun_runner(
    fn: Optional[Callable[[dict[str, Any], Any], dict[str, Any]]]
) -> None:
    """Install the ``validation_rerun`` runner.

    Signature: ``fn(target_spec, client) -> {"run_id": str, ...}``.

    The default-production runner is ``_default_validation_rerun_runner``
    which delegates to ``research.validation_runner
    .run_factor_validation_research``. Tests install a stub that returns a
    fixed run_id without touching Supabase.
    """

    global _VALIDATION_RERUN_RUNNER
    _VALIDATION_RERUN_RUNNER = fn


def set_sandbox_client_factory(fn: Optional[Callable[[], Any]]) -> None:
    """Install a lazy Supabase-client factory for the injected runner.

    Kept separate from ``set_sandbox_validation_rerun_runner`` so tests can
    install a deterministic runner without providing a client.
    """

    global _SANDBOX_CLIENT_FACTORY
    _SANDBOX_CLIENT_FACTORY = fn


def get_sandbox_validation_rerun_runner() -> Optional[
    Callable[[dict[str, Any], Any], dict[str, Any]]
]:
    return _VALIDATION_RERUN_RUNNER


def get_sandbox_client_factory() -> Optional[Callable[[], Any]]:
    return _SANDBOX_CLIENT_FACTORY


def _default_validation_rerun_runner(
    target_spec: dict[str, Any], client: Any
) -> dict[str, Any]:
    """Production runner: re-run the canonical factor_validation for the
    target_spec via ``run_factor_validation_research``.

    The returned dict always contains at least ``{"run_id": str}``. Extra
    keys (``status``, ``factors_ok``, ...) are passed through and recorded
    on the result packet's ``produced_refs[*].details`` for lineage.
    """

    from research.validation_runner import run_factor_validation_research

    res = run_factor_validation_research(
        client,
        universe_name=str(target_spec.get("universe_name") or ""),
        horizon_type=str(target_spec.get("horizon_type") or ""),
    )
    run_id = str(res.get("run_id") or "")
    if not run_id:
        raise RuntimeError(
            "run_factor_validation_research returned empty run_id; "
            "cannot record completed sandbox result"
        )
    return {
        "run_id": run_id,
        "status": str(res.get("status") or ""),
        "factors_ok": int(res.get("factors_ok") or 0),
        "factors_failed": int(res.get("factors_failed") or 0),
        "validation_panels_used": int(res.get("validation_panels_used") or 0),
        "symbols_in_slice": int(res.get("symbols_in_slice") or 0),
    }


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_result_for_request(
    store: HarnessStoreProtocol, *, request_packet_id: str
) -> Optional[dict[str, Any]]:
    """Return any previously-emitted ``SandboxResultPacketV1`` citing the
    given request_packet_id, so the worker stays idempotent across retries.
    """

    rows = store.list_packets(
        packet_type="SandboxResultPacketV1", limit=500
    )
    for r in rows:
        payload = r.get("payload") or {}
        if str(payload.get("cited_request_packet_id") or "") == request_packet_id:
            return r
    return None


def _emit_result_packet(
    store: HarnessStoreProtocol,
    *,
    request_packet: dict[str, Any],
    outcome: str,
    produced_refs: list[dict[str, Any]],
    blocking_reasons: list[str],
    now_iso: str,
) -> str:
    req_id = str(request_packet.get("packet_id") or "")
    req_payload = request_packet.get("payload") or {}
    request_id = str(req_payload.get("request_id") or "")
    sandbox_kind = str(req_payload.get("sandbox_kind") or "")
    registry_entry_id = str(req_payload.get("registry_entry_id") or "")
    horizon = str(req_payload.get("horizon") or "")

    result_id = "srs_" + deterministic_packet_id(
        packet_type="SandboxResultPacketV1",
        created_by_agent="layer3.sandbox_executor_v1",
        target_scope={
            "request_id": request_id,
            "outcome": outcome,
        },
        salt=now_iso,
    ).removeprefix("pkt_")

    pid = deterministic_packet_id(
        packet_type="SandboxResultPacketV1",
        created_by_agent="layer3.sandbox_executor_v1",
        target_scope={
            "request_id": request_id,
            "cited_request_packet_id": req_id,
            "outcome": outcome,
        },
        salt=now_iso,
    )

    payload = {
        "result_id": result_id,
        "cited_request_packet_id": req_id,
        "outcome": outcome,
        "produced_refs": list(produced_refs or []),
        "blocking_reasons": list(blocking_reasons or []),
        "completed_at_utc": now_iso,
        "sandbox_kind": sandbox_kind,
        "registry_entry_id": registry_entry_id,
        "horizon": horizon,
    }

    pkt = SandboxResultPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "SandboxResultPacketV1",
            "target_layer": "layer3_research",
            "created_by_agent": "layer3.sandbox_executor_v1",
            "created_at_utc": now_iso,
            "target_scope": {
                "request_id": request_id,
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
                "sandbox_kind": sandbox_kind,
            },
            "provenance_refs": [f"packet:{req_id}"],
            "cited_parent_packet_ids": [
                f"SandboxRequestPacketV1:{req_id}"
            ],
            "confidence": 1.0 if outcome == "completed" else 0.5,
            "blocking_reasons": list(blocking_reasons or []),
            "status": "done",
            "payload": payload,
        }
    )
    store.upsert_packet(pkt.model_dump())
    return pkt.packet_id


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def enqueue_sandbox_request(
    store: HarnessStoreProtocol,
    *,
    request_id: str,
    sandbox_kind: str,
    registry_entry_id: str,
    horizon: str,
    target_spec: dict[str, Any],
    requested_by: str,
    cited_evidence_packet_ids: list[str],
    cited_ask_packet_id: Optional[str] = None,
    now_iso: Optional[str] = None,
) -> dict[str, Any]:
    """Record a ``SandboxRequestPacketV1`` and enqueue a ``sandbox_queue``
    job pointing at it.

    Returns ``{ok, request_packet_id, job_id}`` on success, or
    ``{ok: False, error}`` if the packet contract rejects the payload or
    an active job already exists for this packet_id (idempotency).
    """

    now = now_iso or _now_iso()
    if sandbox_kind not in SANDBOX_KINDS:
        return {
            "ok": False,
            "error": (
                f"sandbox_kind_not_allowed:{sandbox_kind!r} "
                f"(allowed={SANDBOX_KINDS})"
            ),
        }

    pid = deterministic_packet_id(
        packet_type="SandboxRequestPacketV1",
        created_by_agent="layer3.sandbox_executor_v1",
        target_scope={
            "request_id": request_id,
            "sandbox_kind": sandbox_kind,
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
        },
        salt=now,
    )

    payload = {
        "request_id": request_id,
        "sandbox_kind": sandbox_kind,
        "registry_entry_id": registry_entry_id,
        "horizon": horizon,
        "target_spec": dict(target_spec or {}),
        "requested_by": requested_by,
        "cited_evidence_packet_ids": list(cited_evidence_packet_ids or []),
        "queued_at_utc": now,
    }
    if cited_ask_packet_id:
        payload["cited_ask_packet_id"] = cited_ask_packet_id

    try:
        pkt = SandboxRequestPacketV1.model_validate(
            {
                "packet_id": pid,
                "packet_type": "SandboxRequestPacketV1",
                "target_layer": "layer3_research",
                "created_by_agent": "layer3.sandbox_executor_v1",
                "created_at_utc": now,
                "target_scope": {
                    "request_id": request_id,
                    "registry_entry_id": registry_entry_id,
                    "horizon": horizon,
                    "sandbox_kind": sandbox_kind,
                },
                "provenance_refs": [
                    f"packet:{p}" for p in (cited_evidence_packet_ids or [])
                ],
                "cited_parent_packet_ids": list(
                    cited_evidence_packet_ids or []
                ),
                "confidence": 1.0,
                "blocking_reasons": [],
                "status": "enqueued",
                "payload": payload,
            }
        )
    except Exception as exc:
        return {"ok": False, "error": f"request_validation_failed:{exc}"}

    store.upsert_packet(pkt.model_dump())

    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="sandbox_queue",
                packet_id=pkt.packet_id,
                salt=now,
            ),
            "queue_class": "sandbox_queue",
            "packet_id": pkt.packet_id,
            "not_before_utc": now,
            "worker_agent": "layer3.sandbox_executor_v1",
        }
    )
    try:
        store.enqueue_job(job.model_dump())
    except StoreError as exc:
        return {
            "ok": True,
            "request_packet_id": pkt.packet_id,
            "job_id": None,
            "idempotent_skip": True,
            "detail": f"{exc}",
        }
    return {
        "ok": True,
        "request_packet_id": pkt.packet_id,
        "job_id": job.job_id,
    }


def sandbox_queue_worker(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Worker for ``sandbox_queue``.

    Return shape follows the scheduler / worker contract:

    * Completed: ``{ok: True, outcome: 'completed', result_packet_id, produced_refs}``
    * Blocked   : ``{ok: True, outcome: 'blocked_insufficient_inputs' | 'rejected_kind_not_allowed' | 'no_change' | 'errored', result_packet_id, blocking_reasons}``
    * Idempotent skip: ``{ok: True, skipped: True, reason, result_packet_id}``
    * Failure (DLQ): ``{ok: False, error, retryable: False}``
    """

    req_id = str(job_row.get("packet_id") or "")
    if not req_id:
        return {
            "ok": False,
            "error": "job_row.packet_id missing",
            "retryable": False,
        }

    req = store.get_packet(req_id)
    if req is None:
        return {
            "ok": False,
            "error": f"request_missing:{req_id}",
            "retryable": False,
        }
    if str(req.get("packet_type") or "") != "SandboxRequestPacketV1":
        return {
            "ok": False,
            "error": (
                f"wrong_packet_type:{req.get('packet_type')!r} for {req_id}"
            ),
            "retryable": False,
        }

    existing = _existing_result_for_request(store, request_packet_id=req_id)
    if existing is not None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "result_already_emitted",
            "result_packet_id": str(existing.get("packet_id") or ""),
        }

    payload = req.get("payload") or {}
    sandbox_kind = str(payload.get("sandbox_kind") or "")
    now_iso = _now_iso()

    if sandbox_kind not in SANDBOX_KINDS:
        result_id = _emit_result_packet(
            store,
            request_packet=req,
            outcome="rejected_kind_not_allowed",
            produced_refs=[],
            blocking_reasons=[
                f"sandbox_kind_not_allowed:{sandbox_kind!r} "
                f"(allowed={SANDBOX_KINDS})"
            ],
            now_iso=now_iso,
        )
        store.set_packet_status(req_id, "blocked")
        return {
            "ok": True,
            "outcome": "rejected_kind_not_allowed",
            "result_packet_id": result_id,
            "blocking_reasons": [
                f"sandbox_kind_not_allowed:{sandbox_kind!r}"
            ],
        }

    target_spec = payload.get("target_spec") or {}
    runner = _VALIDATION_RERUN_RUNNER
    client_factory = _SANDBOX_CLIENT_FACTORY
    client: Any = None
    blocking_reasons: list[str] = []
    if runner is None:
        if client_factory is None:
            blocking_reasons.append(
                "no_sandbox_validation_rerun_runner_installed"
            )
        else:
            runner = _default_validation_rerun_runner
    if runner is not None and client_factory is not None:
        try:
            client = client_factory()
        except Exception as exc:  # pragma: no cover - defensive
            blocking_reasons.append(f"client_factory_failed:{exc}")
            client = None

    if runner is None or (runner is _default_validation_rerun_runner and client is None):
        if not blocking_reasons:
            blocking_reasons.append("no_supabase_client_for_validation_rerun")
        result_id = _emit_result_packet(
            store,
            request_packet=req,
            outcome="blocked_insufficient_inputs",
            produced_refs=[],
            blocking_reasons=blocking_reasons,
            now_iso=now_iso,
        )
        store.set_packet_status(req_id, "blocked")
        return {
            "ok": True,
            "outcome": "blocked_insufficient_inputs",
            "result_packet_id": result_id,
            "blocking_reasons": blocking_reasons,
        }

    try:
        runner_result = runner(dict(target_spec), client)
    except Exception as exc:  # noqa: BLE001
        result_id = _emit_result_packet(
            store,
            request_packet=req,
            outcome="errored",
            produced_refs=[],
            blocking_reasons=[f"runner_exception:{exc}"],
            now_iso=now_iso,
        )
        store.set_packet_status(req_id, "blocked")
        log.exception(
            "sandbox_queue_worker validation_rerun runner failed request=%s",
            req_id,
        )
        return {
            "ok": True,
            "outcome": "errored",
            "result_packet_id": result_id,
            "blocking_reasons": [f"runner_exception:{exc}"],
        }

    run_id = str((runner_result or {}).get("run_id") or "")
    if not run_id:
        result_id = _emit_result_packet(
            store,
            request_packet=req,
            outcome="errored",
            produced_refs=[],
            blocking_reasons=["runner_returned_empty_run_id"],
            now_iso=now_iso,
        )
        store.set_packet_status(req_id, "blocked")
        return {
            "ok": True,
            "outcome": "errored",
            "result_packet_id": result_id,
            "blocking_reasons": ["runner_returned_empty_run_id"],
        }

    produced_refs = [
        {
            "kind": "factor_validation_run_id",
            "id": run_id,
            "details": {
                k: runner_result[k]
                for k in (
                    "status",
                    "factors_ok",
                    "factors_failed",
                    "validation_panels_used",
                    "symbols_in_slice",
                )
                if k in (runner_result or {})
            },
        }
    ]
    result_id = _emit_result_packet(
        store,
        request_packet=req,
        outcome="completed",
        produced_refs=produced_refs,
        blocking_reasons=[],
        now_iso=now_iso,
    )
    store.set_packet_status(req_id, "done")
    log.info(
        "sandbox_queue_worker validation_rerun completed request=%s "
        "factor_validation_run_id=%s",
        req_id,
        run_id,
    )
    return {
        "ok": True,
        "outcome": "completed",
        "result_packet_id": result_id,
        "produced_refs": produced_refs,
    }
