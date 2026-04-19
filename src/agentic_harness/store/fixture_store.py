"""In-memory fixture store for the agentic harness.

Deterministic and network-free: tests and evidence generation drive the full
harness over this store. Enforces the same idempotency invariants as the
Supabase-backed implementation.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Optional

from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError, now_utc_iso


_ACTIVE_JOB_STATUSES = ("enqueued", "running")


class FixtureHarnessStore(HarnessStoreProtocol):
    def __init__(self) -> None:
        self._packets: dict[str, dict[str, Any]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._ticks: list[dict[str, Any]] = []

    # --- packets -------------------------------------------------------------

    def upsert_packet(self, row: dict[str, Any]) -> dict[str, Any]:
        pid = str(row.get("packet_id") or "")
        if not pid:
            raise StoreError("packet_id required")
        cloned = copy.deepcopy(row)
        cloned.setdefault("created_at_utc", now_utc_iso())
        cloned["updated_at_utc"] = now_utc_iso()
        self._packets[pid] = cloned
        return copy.deepcopy(cloned)

    def set_packet_status(self, packet_id: str, status: str) -> None:
        p = self._packets.get(packet_id)
        if p is None:
            raise StoreError(f"packet not found: {packet_id}")
        p["status"] = status
        p["updated_at_utc"] = now_utc_iso()

    def get_packet(self, packet_id: str) -> Optional[dict[str, Any]]:
        p = self._packets.get(packet_id)
        return copy.deepcopy(p) if p is not None else None

    def list_packets(
        self,
        *,
        packet_type: Optional[str] = None,
        target_layer: Optional[str] = None,
        status: Optional[str] = None,
        since_utc: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in self._packets.values():
            if packet_type and p.get("packet_type") != packet_type:
                continue
            if target_layer and p.get("target_layer") != target_layer:
                continue
            if status and p.get("status") != status:
                continue
            if since_utc and str(p.get("created_at_utc") or "") < since_utc:
                continue
            out.append(copy.deepcopy(p))
        out.sort(key=lambda r: str(r.get("created_at_utc") or ""), reverse=True)
        return out[: max(1, int(limit))]

    def count_packets_by_layer(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self._packets.values():
            layer = str(p.get("target_layer") or "unknown")
            counts[layer] = counts.get(layer, 0) + 1
        return counts

    # --- queue ---------------------------------------------------------------

    def enqueue_job(self, row: dict[str, Any]) -> dict[str, Any]:
        jid = str(row.get("job_id") or "")
        if not jid:
            raise StoreError("job_id required")
        qc = str(row.get("queue_class") or "")
        pid = str(row.get("packet_id") or "")
        if pid not in self._packets:
            raise StoreError(f"packet_id not in store: {pid}")
        for j in self._jobs.values():
            if (
                j.get("queue_class") == qc
                and j.get("packet_id") == pid
                and j.get("status") in _ACTIVE_JOB_STATUSES
            ):
                raise StoreError(
                    f"duplicate active job for ({qc}, {pid}); existing job_id={j.get('job_id')}"
                )
        cloned = copy.deepcopy(row)
        cloned.setdefault("enqueued_at_utc", now_utc_iso())
        cloned.setdefault("not_before_utc", cloned["enqueued_at_utc"])
        cloned.setdefault("attempts", 0)
        cloned.setdefault("max_attempts", 3)
        cloned.setdefault("status", "enqueued")
        cloned.setdefault("worker_agent", "")
        cloned.setdefault("last_error", "")
        cloned.setdefault("result_json", None)
        self._jobs[jid] = cloned
        return copy.deepcopy(cloned)

    def claim_next_jobs(
        self,
        *,
        queue_class: str,
        now_utc: str,
        max_jobs: int = 5,
    ) -> list[dict[str, Any]]:
        candidates = [
            j
            for j in self._jobs.values()
            if j.get("queue_class") == queue_class
            and j.get("status") == "enqueued"
            and str(j.get("not_before_utc") or "") <= str(now_utc or "")
        ]
        candidates.sort(key=lambda r: str(r.get("enqueued_at_utc") or ""))
        claimed: list[dict[str, Any]] = []
        for j in candidates[: max(0, int(max_jobs))]:
            j["status"] = "running"
            j["attempts"] = int(j.get("attempts") or 0) + 1
            claimed.append(copy.deepcopy(j))
        return claimed

    def mark_job_result(
        self,
        *,
        job_id: str,
        status: str,
        result_json: Optional[dict[str, Any]] = None,
        last_error: str = "",
        increment_attempts: bool = False,
    ) -> None:
        j = self._jobs.get(job_id)
        if j is None:
            raise StoreError(f"job not found: {job_id}")
        j["status"] = status
        if result_json is not None:
            j["result_json"] = copy.deepcopy(result_json)
        if last_error:
            j["last_error"] = str(last_error)
        if increment_attempts:
            j["attempts"] = int(j.get("attempts") or 0) + 1

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        j = self._jobs.get(job_id)
        return copy.deepcopy(j) if j is not None else None

    def list_jobs(
        self,
        *,
        queue_class: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for j in self._jobs.values():
            if queue_class and j.get("queue_class") != queue_class:
                continue
            if status and j.get("status") != status:
                continue
            out.append(copy.deepcopy(j))
        out.sort(key=lambda r: str(r.get("enqueued_at_utc") or ""), reverse=True)
        return out[: max(1, int(limit))]

    def queue_depth(self) -> dict[str, int]:
        from agentic_harness.contracts.queues_v1 import QUEUE_CLASSES

        depths: dict[str, int] = {qc: 0 for qc in QUEUE_CLASSES}
        for j in self._jobs.values():
            if j.get("status") == "enqueued":
                qc = str(j.get("queue_class") or "")
                if qc in depths:
                    depths[qc] += 1
        return depths

    # --- scheduler ticks -----------------------------------------------------

    def log_tick(self, *, tick_kind: str, summary: dict[str, Any]) -> dict[str, Any]:
        row = {
            "tick_id": str(uuid.uuid4()),
            "tick_at_utc": now_utc_iso(),
            "tick_kind": str(tick_kind or "harness_tick"),
            "summary": copy.deepcopy(summary or {}),
        }
        self._ticks.append(row)
        return copy.deepcopy(row)

    def last_tick_of_kind(self, tick_kind: str) -> Optional[dict[str, Any]]:
        for t in reversed(self._ticks):
            if t.get("tick_kind") == tick_kind:
                return copy.deepcopy(t)
        return None

    def list_ticks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [copy.deepcopy(t) for t in self._ticks[-max(1, int(limit)) :][::-1]]
