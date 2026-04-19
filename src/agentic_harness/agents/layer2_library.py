"""Layer 2 - Data Quality Verification / Library Management.

Three deterministic agents:

    * ``integrity_sentinel_agent`` - deterministic cheques on the data library
      (PIT violations, stale data, schema drift). Emits ``LibraryIntegrityPacketV1``.
    * ``coverage_curator_agent`` - cohort-holes sweep. Emits ``CoverageGapPacketV1``.
    * ``artifact_librarian_agent`` - for severity ≥ ``medium`` enqueues a
      ``quality_queue`` job that asks a human/operator downstream to bind a
      canonical source. ``high`` severity additionally flips packet status to
      ``escalated`` so operators see it immediately.

Like Layer 1, side-effects are limited to packet + queue writes. The layer
never mutates the library itself.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    CoverageGapPacketV1,
    LibraryIntegrityPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError


# ---------------------------------------------------------------------------
# Inputs injectable for tests.
# ---------------------------------------------------------------------------


LibraryInspector = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
"""(store, now_iso) -> list of issue dicts shaped like LibraryIntegrityPacketV1.payload."""

CoverageInspector = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
"""(store, now_iso) -> list of gap dicts shaped like CoverageGapPacketV1.payload."""


_LIBRARY_INSPECTOR: Optional[LibraryInspector] = None
_COVERAGE_INSPECTOR: Optional[CoverageInspector] = None


def set_library_inspector(fn: Optional[LibraryInspector]) -> None:
    global _LIBRARY_INSPECTOR
    _LIBRARY_INSPECTOR = fn


def set_coverage_inspector(fn: Optional[CoverageInspector]) -> None:
    global _COVERAGE_INSPECTOR
    _COVERAGE_INSPECTOR = fn


def _default_library_inspector(store, now_iso):
    return []


def _default_coverage_inspector(store, now_iso):
    return []


# ---------------------------------------------------------------------------
# Integrity Sentinel / Coverage Curator / Artifact Librarian
# ---------------------------------------------------------------------------


def _severity_rank(s: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(s or "low"), 0)


def integrity_sentinel_agent(
    store: HarnessStoreProtocol, now_iso: str
) -> list[LibraryIntegrityPacketV1]:
    inspector = _LIBRARY_INSPECTOR or _default_library_inspector
    issues = inspector(store, now_iso) or []
    packets: list[LibraryIntegrityPacketV1] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        check = str(issue.get("check_name") or "")
        sev = str(issue.get("severity") or "low")
        refs = list(issue.get("offending_refs") or [])
        pid = deterministic_packet_id(
            packet_type="LibraryIntegrityPacketV1",
            created_by_agent="integrity_sentinel_agent",
            target_scope={"check_name": check, "refs_count": str(len(refs))},
            salt=str(issue.get("summary") or ""),
        )
        pkt = LibraryIntegrityPacketV1.model_validate(
            {
                "packet_id": pid,
                "packet_type": "LibraryIntegrityPacketV1",
                "target_layer": "layer2_library",
                "created_by_agent": "integrity_sentinel_agent",
                "target_scope": {
                    "check_name": check,
                    "cohort": str(issue.get("cohort") or ""),
                },
                "provenance_refs": list(issue.get("provenance_refs") or ["library://self-check"]),
                "confidence": float(issue.get("confidence", 0.8)),
                "payload": {
                    "check_name": check,
                    "severity": sev,
                    "offending_refs": refs,
                    "summary": str(issue.get("summary") or ""),
                },
                "status": "escalated" if sev == "high" else "proposed",
            }
        )
        packets.append(pkt)
    return packets


def coverage_curator_agent(
    store: HarnessStoreProtocol, now_iso: str
) -> list[CoverageGapPacketV1]:
    inspector = _COVERAGE_INSPECTOR or _default_coverage_inspector
    gaps = inspector(store, now_iso) or []
    packets: list[CoverageGapPacketV1] = []
    for g in gaps:
        if not isinstance(g, dict):
            continue
        cohort = str(g.get("cohort_name") or "")
        missing = list(g.get("missing_asset_ids") or [])
        dim = str(g.get("dimension") or "transcripts_last_90d")
        pid = deterministic_packet_id(
            packet_type="CoverageGapPacketV1",
            created_by_agent="coverage_curator_agent",
            target_scope={"cohort_name": cohort, "dimension": dim},
            salt=",".join(sorted(missing)),
        )
        pkt = CoverageGapPacketV1.model_validate(
            {
                "packet_id": pid,
                "packet_type": "CoverageGapPacketV1",
                "target_layer": "layer2_library",
                "created_by_agent": "coverage_curator_agent",
                "target_scope": {"cohort_name": cohort, "dimension": dim},
                "provenance_refs": list(g.get("provenance_refs") or [f"cohort://{cohort}"]),
                "confidence": float(g.get("confidence", 0.7)),
                "payload": {
                    "cohort_name": cohort,
                    "missing_asset_ids": missing,
                    "dimension": dim,
                },
            }
        )
        packets.append(pkt)
    return packets


def artifact_librarian_agent(
    *,
    store: HarnessStoreProtocol,
    integrity_packets: list[LibraryIntegrityPacketV1],
    coverage_packets: list[CoverageGapPacketV1],
    now_iso: str,
) -> dict[str, Any]:
    enqueued_ids: list[str] = []
    escalated_ids: list[str] = []
    for p in integrity_packets:
        store.upsert_packet(p.model_dump())
        sev = str((p.payload or {}).get("severity") or "low")
        if _severity_rank(sev) >= _severity_rank("medium"):
            job = QueueJobV1.model_validate(
                {
                    "job_id": deterministic_job_id(
                        queue_class="quality_queue",
                        packet_id=p.packet_id,
                        salt=now_iso,
                    ),
                    "queue_class": "quality_queue",
                    "packet_id": p.packet_id,
                    "not_before_utc": now_iso,
                    "worker_agent": "artifact_librarian_worker",
                }
            )
            try:
                store.enqueue_job(job.model_dump())
                enqueued_ids.append(job.job_id)
            except StoreError:
                pass
        if sev == "high":
            escalated_ids.append(p.packet_id)
    for p in coverage_packets:
        store.upsert_packet(p.model_dump())
        # Coverage gaps always get a quality_queue job so ops can follow up.
        job = QueueJobV1.model_validate(
            {
                "job_id": deterministic_job_id(
                    queue_class="quality_queue",
                    packet_id=p.packet_id,
                    salt=now_iso,
                ),
                "queue_class": "quality_queue",
                "packet_id": p.packet_id,
                "not_before_utc": now_iso,
                "worker_agent": "artifact_librarian_worker",
            }
        )
        try:
            store.enqueue_job(job.model_dump())
            enqueued_ids.append(job.job_id)
        except StoreError:
            pass
    return {
        "integrity_packet_count": len(integrity_packets),
        "coverage_packet_count": len(coverage_packets),
        "enqueued_quality_jobs": enqueued_ids,
        "escalated_packet_ids": escalated_ids,
    }


def propose_layer2_cadence(
    store: HarnessStoreProtocol, now_iso: str
) -> dict[str, Any]:
    ip = integrity_sentinel_agent(store, now_iso)
    cp = coverage_curator_agent(store, now_iso)
    return artifact_librarian_agent(
        store=store, integrity_packets=ip, coverage_packets=cp, now_iso=now_iso
    )


# ---------------------------------------------------------------------------
# Queue worker: quality_queue
# ---------------------------------------------------------------------------


def quality_queue_worker(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    """Deterministic worker: mark the underlying packet as escalated so an
    operator sees it in ``harness-status``. The worker does not fix the data
    itself - it only acknowledges the issue and records the triage.
    """

    pid = str(job_row.get("packet_id") or "")
    pkt = store.get_packet(pid)
    if pkt is None:
        return {"ok": False, "error": f"packet_missing: {pid}"}
    store.set_packet_status(pid, "escalated")
    return {
        "ok": True,
        "triaged_packet_id": pid,
        "triaged_status": "escalated",
    }
