"""``run_one_tick`` — single-shot in-process harness tick.

The scheduler is intentionally boring. It does three things:

  1. For each registered cadence, call the layer's ``propose_fn`` to seed new
     packets / jobs when the cadence is due.
  2. For each queue class, claim up to ``max_jobs_per_queue`` ``enqueued``
     jobs whose ``not_before_utc <= now_utc`` and run their worker.
  3. Append a ``scheduler_ticks`` row that summarises what happened (for
     ``harness-status`` observability).

Layer-specific logic lives in ``src/agentic_harness/agents/layerN_*.py``;
this module never branches on packet_type / layer semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from agentic_harness.contracts.queues_v1 import QUEUE_CLASSES
from agentic_harness.scheduler.cadences import DEFAULT_CADENCES, should_run_cadence
from agentic_harness.store.protocol import HarnessStoreProtocol


LayerProposeFn = Callable[[HarnessStoreProtocol, str], dict[str, Any]]
"""(store, now_utc_iso) -> summary dict. May enqueue jobs as side effect."""

QueueWorkerFn = Callable[[HarnessStoreProtocol, dict[str, Any]], dict[str, Any]]
"""(store, job_row) -> result dict with optional 'ok': bool and 'error': str."""


@dataclass(frozen=True)
class LayerCadenceSpec:
    cadence_key: str
    propose_fn: LayerProposeFn


@dataclass(frozen=True)
class QueueSpec:
    queue_class: str
    worker_fn: QueueWorkerFn


@dataclass
class TickSummary:
    tick_at_utc: str
    dry_run: bool = False
    cadence_decisions: dict[str, str] = field(default_factory=dict)
    layer_summaries: dict[str, Any] = field(default_factory=dict)
    queue_runs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tick_at_utc": self.tick_at_utc,
            "dry_run": self.dry_run,
            "cadence_decisions": dict(self.cadence_decisions),
            "layer_summaries": dict(self.layer_summaries),
            "queue_runs": dict(self.queue_runs),
        }


def _utc_iso(dt: Optional[datetime]) -> str:
    dt = dt or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _compute_next_not_before(now_iso: str, backoff_s: int) -> str:
    """Return an ISO-8601 timestamp ``backoff_s`` seconds after ``now_iso``.

    Falls back to "now + backoff" from wall-clock if ``now_iso`` can't be
    parsed (shouldn't happen in practice but keeps the scheduler robust).
    """

    try:
        base = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        base = datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(seconds=max(0, int(backoff_s)))).isoformat()


def run_one_tick(
    *,
    store: HarnessStoreProtocol,
    layer_cadences: list[LayerCadenceSpec],
    queue_specs: list[QueueSpec],
    now: Optional[datetime] = None,
    max_jobs_per_queue: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    now_iso = _utc_iso(now)
    summary = TickSummary(tick_at_utc=now_iso, dry_run=bool(dry_run))

    # --- 1) cadence-based seeding ------------------------------------------
    for spec in layer_cadences:
        last_tick = store.last_tick_of_kind(f"cadence:{spec.cadence_key}")
        last_at = (last_tick or {}).get("tick_at_utc")
        due = should_run_cadence(
            cadence_key=spec.cadence_key,
            last_run_at_utc=last_at,
            now_utc=now or datetime.now(timezone.utc),
        )
        if not due:
            summary.cadence_decisions[spec.cadence_key] = "skipped"
            continue
        summary.cadence_decisions[spec.cadence_key] = "ran"
        if dry_run:
            summary.layer_summaries[spec.cadence_key] = {"dry_run": True}
            continue
        try:
            res = spec.propose_fn(store, now_iso)
        except Exception as e:  # surface but do not abort tick
            summary.layer_summaries[spec.cadence_key] = {"error": str(e)}
            continue
        summary.layer_summaries[spec.cadence_key] = res
        store.log_tick(
            tick_kind=f"cadence:{spec.cadence_key}",
            summary={"result": res},
        )

    # --- 2) drain queues ---------------------------------------------------
    if dry_run:
        summary.queue_runs = {qc: {"dry_run": True} for qc in QUEUE_CLASSES}
    else:
        worker_by_queue = {qs.queue_class: qs.worker_fn for qs in queue_specs}
        for qc in QUEUE_CLASSES:
            worker = worker_by_queue.get(qc)
            if worker is None:
                summary.queue_runs[qc] = {"claimed": 0, "reason": "no_worker_registered"}
                continue
            claimed = store.claim_next_jobs(
                queue_class=qc,
                now_utc=now_iso,
                max_jobs=max_jobs_per_queue,
            )
            qsum = {"claimed": len(claimed), "done": 0, "dlq": 0, "errors": []}
            for job in claimed:
                try:
                    result = worker(store, job)
                except Exception as e:
                    result = {"ok": False, "error": str(e)}
                jid = str(job.get("job_id"))
                if result.get("ok", False):
                    store.mark_job_result(
                        job_id=jid, status="done", result_json=dict(result)
                    )
                    qsum["done"] += 1
                else:
                    err = str(result.get("error") or "unknown")
                    # Workers that don't return `retryable` (legacy path)
                    # default to retryable-true so `max_attempts` still
                    # governs final DLQ decisions.  The live FMP adapter
                    # sets this flag explicitly so auth/config errors
                    # fail-fast without burning retry budget.
                    retryable = bool(result.get("retryable", True))
                    attempts_so_far = int(job.get("attempts") or 0)
                    max_attempts = int(job.get("max_attempts") or 3)
                    if (not retryable) or attempts_so_far >= max_attempts:
                        store.mark_job_result(
                            job_id=jid,
                            status="dlq",
                            result_json=dict(result),
                            last_error=err,
                        )
                        qsum["dlq"] += 1
                    else:
                        # Exponential backoff: 5m, 10m, 20m, 40m, …, cap 1h.
                        backoff_s = min(
                            3600, 300 * (2 ** max(0, attempts_so_far - 1))
                        )
                        next_not_before = _compute_next_not_before(
                            now_iso, backoff_s
                        )
                        store.mark_job_result(
                            job_id=jid,
                            status="enqueued",
                            result_json=dict(result),
                            last_error=err,
                            next_not_before_utc=next_not_before,
                        )
                    qsum["errors"].append({"job_id": jid, "error": err})
            summary.queue_runs[qc] = qsum

    # --- 3) log the tick itself --------------------------------------------
    if not dry_run:
        store.log_tick(tick_kind="harness_tick", summary=summary.as_dict())
    return summary.as_dict()


def default_cadences_keys() -> list[str]:
    return list(DEFAULT_CADENCES.keys())
