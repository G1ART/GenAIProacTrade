"""AGH v1 Patch 9 C·A2 — packet / queue-job retention archive.

Closes CF-8·A from the Patch 8 Scale Readiness Note. The two active
tables (``agentic_harness_packets_v1`` and ``agentic_harness_queue_jobs_v1``)
grow without bound; the archive pattern moves aged rows into matching
``*_archive`` tables so live reads stay bounded but the historical
audit trail is preserved.

Design decisions:

* **Copy-then-delete, not copy-or-delete.** Both helpers stage the archive
  insert first and only delete from the active table after the archive
  insert returns successfully. On exception the active table is not
  mutated.
* **Dry-run is always available.** The CLI wrapper (``main.py
  harness-retention-archive --dry-run``) never writes and returns a
  ``ArchiveReport`` the operator can inspect before running for real.
* **Jobs archival is status-gated.** Only terminal-state jobs (``done``,
  ``dlq``, ``expired``) are eligible. Live jobs (``enqueued``, ``running``)
  are never archived, even if their enqueued_at_utc is old — that would
  desync the scheduler.
* **Small batches.** Both helpers page through the selection with a
  bounded batch size (default 500) so a long-running archive cannot
  hold a single long transaction on Supabase.
* **No schema coupling.** We accept a ``supabase.Client`` directly rather
  than the harness store protocol, because the archive tables are not
  part of ``HarnessStoreProtocol`` and we don't want to leak archive
  semantics into every agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

_PACKETS_ACTIVE = "agentic_harness_packets_v1"
_PACKETS_ARCHIVE = "agentic_harness_packets_v1_archive"
_JOBS_ACTIVE = "agentic_harness_queue_jobs_v1"
_JOBS_ARCHIVE = "agentic_harness_queue_jobs_v1_archive"

# Jobs in these statuses are never archived — scheduler will still pick
# them up (``enqueued``) or is already working on them (``running``).
_JOB_TERMINAL_STATUSES = ("done", "dlq", "expired")

# Bounded batch size; see module docstring for why this is capped.
_DEFAULT_BATCH = 500


@dataclass
class ArchiveReport:
    table: str
    cutoff_utc: str
    dry_run: bool
    selected: int = 0
    archived: int = 0
    deleted: int = 0
    batches: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "cutoff_utc": self.cutoff_utc,
            "dry_run": self.dry_run,
            "selected": self.selected,
            "archived": self.archived,
            "deleted": self.deleted,
            "batches": self.batches,
            "errors": list(self.errors),
        }


def _cutoff_iso(days: int) -> str:
    if days < 1:
        raise ValueError("days must be >= 1")
    return (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()


def _strip_projection(row: dict[str, Any], keep: tuple[str, ...]) -> dict[str, Any]:
    return {k: row[k] for k in keep if k in row}


_PACKET_ARCHIVE_COLUMNS = (
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
    "updated_at_utc",
)

_JOB_ARCHIVE_COLUMNS = (
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


def archive_packets_older_than(
    client: Any,
    *,
    days: int,
    batch_size: int = _DEFAULT_BATCH,
    dry_run: bool = False,
) -> ArchiveReport:
    """Copy packets with ``created_at_utc`` older than ``days`` into the
    archive table and delete them from the active table.

    The active table is only mutated after every batch insert returns
    without raising. On exception the rest of the batch is skipped and
    the error is reported; already-processed batches are not rolled
    back (each batch is its own unit of work).
    """
    cutoff = _cutoff_iso(days)
    rep = ArchiveReport(table=_PACKETS_ACTIVE, cutoff_utc=cutoff, dry_run=dry_run)
    while True:
        r = (
            client.table(_PACKETS_ACTIVE)
            .select("*")
            .lt("created_at_utc", cutoff)
            .order("created_at_utc", desc=False)
            .limit(int(batch_size))
            .execute()
        )
        rows = list(r.data or [])
        if not rows:
            break
        rep.selected += len(rows)
        rep.batches += 1
        if dry_run:
            # Avoid an infinite loop when not deleting: only report the
            # first page for dry-run; the operator can re-run without
            # --dry-run for the real pass.
            break
        try:
            projected = [_strip_projection(row, _PACKET_ARCHIVE_COLUMNS) for row in rows]
            client.table(_PACKETS_ARCHIVE).upsert(
                projected, on_conflict="packet_id"
            ).execute()
            rep.archived += len(projected)
        except Exception as exc:
            rep.errors.append(f"archive_insert_failed: {type(exc).__name__}: {exc}")
            break
        try:
            ids = [str(row.get("packet_id") or "") for row in rows if row.get("packet_id")]
            if ids:
                client.table(_PACKETS_ACTIVE).delete().in_("packet_id", ids).execute()
                rep.deleted += len(ids)
        except Exception as exc:
            rep.errors.append(f"active_delete_failed: {type(exc).__name__}: {exc}")
            break
        if len(rows) < batch_size:
            break
    return rep


def archive_jobs_older_than(
    client: Any,
    *,
    days: int,
    batch_size: int = _DEFAULT_BATCH,
    dry_run: bool = False,
) -> ArchiveReport:
    """Copy terminal-state jobs with ``enqueued_at_utc`` older than
    ``days`` into the archive table and delete them from the active
    table. Live jobs (``enqueued``, ``running``) are never archived.
    """
    cutoff = _cutoff_iso(days)
    rep = ArchiveReport(table=_JOBS_ACTIVE, cutoff_utc=cutoff, dry_run=dry_run)
    while True:
        r = (
            client.table(_JOBS_ACTIVE)
            .select("*")
            .lt("enqueued_at_utc", cutoff)
            .in_("status", list(_JOB_TERMINAL_STATUSES))
            .order("enqueued_at_utc", desc=False)
            .limit(int(batch_size))
            .execute()
        )
        rows = list(r.data or [])
        if not rows:
            break
        rep.selected += len(rows)
        rep.batches += 1
        if dry_run:
            break
        try:
            projected = [_strip_projection(row, _JOB_ARCHIVE_COLUMNS) for row in rows]
            client.table(_JOBS_ARCHIVE).upsert(
                projected, on_conflict="job_id"
            ).execute()
            rep.archived += len(projected)
        except Exception as exc:
            rep.errors.append(f"archive_insert_failed: {type(exc).__name__}: {exc}")
            break
        try:
            ids = [str(row.get("job_id") or "") for row in rows if row.get("job_id")]
            if ids:
                client.table(_JOBS_ACTIVE).delete().in_("job_id", ids).execute()
                rep.deleted += len(ids)
        except Exception as exc:
            rep.errors.append(f"active_delete_failed: {type(exc).__name__}: {exc}")
            break
        if len(rows) < batch_size:
            break
    return rep
