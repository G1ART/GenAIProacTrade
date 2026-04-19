"""Supabase-backed implementation of ``HarnessStoreProtocol``.

Uses the existing service-role client constructed via
``src/db/client.py::get_supabase_client`` and wraps the three tables from
``supabase/migrations/20260417120000_agentic_harness_v1.sql``:

    * ``agentic_harness_packets_v1``
    * ``agentic_harness_queue_jobs_v1``
    * ``agentic_harness_scheduler_ticks_v1``

The fixture store shares the same interface so agent/scheduler code doesn't
care which backend it runs against.
"""

from __future__ import annotations

from typing import Any, Optional

from supabase import Client

from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError, now_utc_iso


_PACKETS = "agentic_harness_packets_v1"
_JOBS = "agentic_harness_queue_jobs_v1"
_TICKS = "agentic_harness_scheduler_ticks_v1"
_ACTIVE_JOB_STATUSES = ("enqueued", "running")


# Column allowlists mirror the SQL migration at
# ``supabase/migrations/20260417120000_agentic_harness_v1.sql``. Pydantic
# ``model_dump()`` emits extra fields (``contract``, sometimes empty timestamp
# strings that default to ``""`` on the model) that Postgres rejects. We
# serialize by copying only known columns and dropping empty-string values on
# ``timestamptz`` columns so the DB default (``now()``) wins.

_PACKET_COLUMNS = (
    "packet_id",
    "packet_type",
    "packet_schema_version",
    "target_layer",
    "created_by_agent",
    "created_at_utc",
    "target_scope",
    "provenance_refs",
    "confidence",
    "blocking_reasons",
    "expiry_or_recheck_rule",
    "status",
    "payload",
)

_JOB_COLUMNS = (
    "job_id",
    "queue_class",
    "packet_id",
    "enqueued_at_utc",
    "not_before_utc",
    "attempts",
    "max_attempts",
    "last_error",
    "status",
    "worker_agent",
    "result_json",
)

_JOB_TIMESTAMP_COLUMNS = ("enqueued_at_utc", "not_before_utc")


def _project_row(row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
    return {k: row[k] for k in columns if k in row}


def _scrub_empty_timestamps(row: dict[str, Any], ts_cols: tuple[str, ...]) -> dict[str, Any]:
    out = dict(row)
    for k in ts_cols:
        if k in out and (out[k] is None or out[k] == ""):
            out.pop(k, None)
    return out


class SupabaseHarnessStore(HarnessStoreProtocol):
    def __init__(self, client: Client) -> None:
        self._c = client

    # --- packets -------------------------------------------------------------

    def upsert_packet(self, row: dict[str, Any]) -> dict[str, Any]:
        pid = str(row.get("packet_id") or "")
        if not pid:
            raise StoreError("packet_id required")
        patched = _project_row(row, _PACKET_COLUMNS)
        patched["updated_at_utc"] = now_utc_iso()
        if not str(patched.get("created_at_utc") or "").strip():
            patched.pop("created_at_utc", None)
        r = (
            self._c.table(_PACKETS)
            .upsert(patched, on_conflict="packet_id")
            .execute()
        )
        return dict((r.data or [patched])[0])

    def set_packet_status(self, packet_id: str, status: str) -> None:
        self._c.table(_PACKETS).update(
            {"status": status, "updated_at_utc": now_utc_iso()}
        ).eq("packet_id", packet_id).execute()

    def get_packet(self, packet_id: str) -> Optional[dict[str, Any]]:
        r = (
            self._c.table(_PACKETS)
            .select("*")
            .eq("packet_id", packet_id)
            .limit(1)
            .execute()
        )
        return dict(r.data[0]) if r.data else None

    def list_packets(
        self,
        *,
        packet_type: Optional[str] = None,
        target_layer: Optional[str] = None,
        status: Optional[str] = None,
        since_utc: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        q = self._c.table(_PACKETS).select("*")
        if packet_type:
            q = q.eq("packet_type", packet_type)
        if target_layer:
            q = q.eq("target_layer", target_layer)
        if status:
            q = q.eq("status", status)
        if since_utc:
            q = q.gte("created_at_utc", since_utc)
        r = q.order("created_at_utc", desc=True).limit(max(1, int(limit))).execute()
        return [dict(x) for x in (r.data or [])]

    def count_packets_by_layer(self) -> dict[str, int]:
        r = self._c.table(_PACKETS).select("target_layer").execute()
        counts: dict[str, int] = {}
        for row in r.data or []:
            layer = str(row.get("target_layer") or "unknown")
            counts[layer] = counts.get(layer, 0) + 1
        return counts

    # --- queue ---------------------------------------------------------------

    def enqueue_job(self, row: dict[str, Any]) -> dict[str, Any]:
        jid = str(row.get("job_id") or "")
        if not jid:
            raise StoreError("job_id required")
        qc = str(row.get("queue_class") or "")
        pid = str(row.get("packet_id") or "")
        # Pre-check the idempotency invariant to raise a friendly error
        # before the unique index rejects the row.
        dup = (
            self._c.table(_JOBS)
            .select("job_id,status")
            .eq("queue_class", qc)
            .eq("packet_id", pid)
            .in_("status", list(_ACTIVE_JOB_STATUSES))
            .limit(1)
            .execute()
        )
        if dup.data:
            raise StoreError(
                f"duplicate active job for ({qc}, {pid}); existing job_id={dup.data[0].get('job_id')}"
            )
        payload = _scrub_empty_timestamps(
            _project_row(row, _JOB_COLUMNS), _JOB_TIMESTAMP_COLUMNS
        )
        try:
            r = self._c.table(_JOBS).insert(payload).execute()
        except Exception as e:  # unique index race
            raise StoreError(f"enqueue_job failed: {e}") from e
        return dict((r.data or [payload])[0])

    def claim_next_jobs(
        self,
        *,
        queue_class: str,
        now_utc: str,
        max_jobs: int = 5,
    ) -> list[dict[str, Any]]:
        r = (
            self._c.table(_JOBS)
            .select("*")
            .eq("queue_class", queue_class)
            .eq("status", "enqueued")
            .lte("not_before_utc", now_utc)
            .order("enqueued_at_utc", desc=False)
            .limit(max(0, int(max_jobs)))
            .execute()
        )
        rows = [dict(x) for x in (r.data or [])]
        claimed: list[dict[str, Any]] = []
        for row in rows:
            jid = str(row["job_id"])
            upd = self._c.table(_JOBS).update(
                {
                    "status": "running",
                    "attempts": int(row.get("attempts") or 0) + 1,
                }
            ).eq("job_id", jid).eq("status", "enqueued").execute()
            if upd.data:
                nr = dict(upd.data[0])
                claimed.append(nr)
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
        upd: dict[str, Any] = {"status": status}
        if result_json is not None:
            upd["result_json"] = result_json
        if last_error:
            upd["last_error"] = str(last_error)
        if increment_attempts:
            existing = self.get_job(job_id)
            upd["attempts"] = int((existing or {}).get("attempts") or 0) + 1
        self._c.table(_JOBS).update(upd).eq("job_id", job_id).execute()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        r = (
            self._c.table(_JOBS)
            .select("*")
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        return dict(r.data[0]) if r.data else None

    def list_jobs(
        self,
        *,
        queue_class: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        q = self._c.table(_JOBS).select("*")
        if queue_class:
            q = q.eq("queue_class", queue_class)
        if status:
            q = q.eq("status", status)
        r = q.order("enqueued_at_utc", desc=True).limit(max(1, int(limit))).execute()
        return [dict(x) for x in (r.data or [])]

    def queue_depth(self) -> dict[str, int]:
        from agentic_harness.contracts.queues_v1 import QUEUE_CLASSES

        depths: dict[str, int] = {qc: 0 for qc in QUEUE_CLASSES}
        r = (
            self._c.table(_JOBS)
            .select("queue_class,status")
            .eq("status", "enqueued")
            .execute()
        )
        for row in r.data or []:
            qc = str(row.get("queue_class") or "")
            if qc in depths:
                depths[qc] += 1
        return depths

    # --- scheduler ticks -----------------------------------------------------

    def log_tick(self, *, tick_kind: str, summary: dict[str, Any]) -> dict[str, Any]:
        row = {
            "tick_kind": str(tick_kind or "harness_tick"),
            "summary": dict(summary or {}),
        }
        r = self._c.table(_TICKS).insert(row).execute()
        return dict((r.data or [row])[0])

    def last_tick_of_kind(self, tick_kind: str) -> Optional[dict[str, Any]]:
        r = (
            self._c.table(_TICKS)
            .select("*")
            .eq("tick_kind", tick_kind)
            .order("tick_at_utc", desc=True)
            .limit(1)
            .execute()
        )
        return dict(r.data[0]) if r.data else None

    def list_ticks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        r = (
            self._c.table(_TICKS)
            .select("*")
            .order("tick_at_utc", desc=True)
            .limit(max(1, int(limit)))
            .execute()
        )
        return [dict(x) for x in (r.data or [])]
