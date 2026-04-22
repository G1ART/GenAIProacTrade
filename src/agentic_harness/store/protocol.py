"""Shared store protocol so fixture and Supabase backends are interchangeable.

All scheduler / agent code is written against ``HarnessStoreProtocol``. This
is what lets tests drive the full harness over an in-memory fixture store
with zero network access while production operation uses the Supabase
backed store.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Protocol, runtime_checkable


class StoreError(RuntimeError):
    """Raised when a store rejects an operation (e.g. duplicate active job)."""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@runtime_checkable
class HarnessStoreProtocol(Protocol):
    # --- packets -------------------------------------------------------------

    def upsert_packet(self, row: dict[str, Any]) -> dict[str, Any]:
        ...

    def set_packet_status(self, packet_id: str, status: str) -> None:
        ...

    def get_packet(self, packet_id: str) -> Optional[dict[str, Any]]:
        ...

    def list_packets(
        self,
        *,
        packet_type: Optional[str] = None,
        target_layer: Optional[str] = None,
        status: Optional[str] = None,
        since_utc: Optional[str] = None,
        target_asset_id: Optional[str] = None,
        target_horizon: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """AGH v1 Patch 9 C·B2 — ``target_asset_id`` / ``target_horizon``
        push the JSONB equality filter into the DB so routers no longer
        have to pull the full packet set and filter in Python. Backends
        that can't push the filter server-side must still apply it
        (fixture store filters in-memory)."""
        ...

    def count_packets_by_layer(self) -> dict[str, int]:
        ...

    # --- queue ---------------------------------------------------------------

    def enqueue_job(self, row: dict[str, Any]) -> dict[str, Any]:
        """Insert a job. Raise ``StoreError`` if another active job already
        exists for the same ``(queue_class, packet_id)``."""

    def claim_next_jobs(
        self,
        *,
        queue_class: str,
        now_utc: str,
        max_jobs: int = 5,
    ) -> list[dict[str, Any]]:
        """Claim up to ``max_jobs`` jobs whose ``not_before_utc <= now_utc``
        and transition them to ``running``. Returns the claimed rows."""

    def mark_job_result(
        self,
        *,
        job_id: str,
        status: str,
        result_json: Optional[dict[str, Any]] = None,
        last_error: str = "",
        increment_attempts: bool = False,
        next_not_before_utc: Optional[str] = None,
    ) -> None:
        """Update a job row.

        ``next_not_before_utc`` is honored only when ``status == 'enqueued'``
        so that re-queued jobs observe a scheduler-imposed backoff window.
        For any other status the argument is ignored.
        """

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        ...

    def list_jobs(
        self,
        *,
        queue_class: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        ...

    def queue_depth(self) -> dict[str, int]:
        """Return ``{queue_class: depth_of_enqueued_jobs}``."""

    # --- scheduler ticks -----------------------------------------------------

    def log_tick(self, *, tick_kind: str, summary: dict[str, Any]) -> dict[str, Any]:
        ...

    def last_tick_of_kind(self, tick_kind: str) -> Optional[dict[str, Any]]:
        ...

    def list_ticks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        ...
