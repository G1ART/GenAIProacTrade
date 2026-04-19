"""Layer 1 - Proactive Data Collection Layer.

Three deterministic (non-LLM) agents:

    * ``source_scout_agent`` - compare the active Today registry assets against
      the last known fetch for each source family, return stale candidates.
    * ``event_trigger_agent`` - wrap each candidate in an ``EventTriggerPacketV1``.
    * ``ingest_coordinator_agent`` - wrap the trigger in an ``IngestAlertPacketV1``
      and enqueue it on ``ingest_queue``. **Never** mutates the Today registry
      itself - its only side-effect is packet + queue writes.

The transcripts-adapter worker (``ingest_queue_worker``) is what the scheduler
invokes when claiming a job. It delegates the actual transcript fetch to a
swappable callable registered via ``set_transcript_fetcher`` so tests can
drive the full vertical path without network access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from agentic_harness.contracts.packets_v1 import (
    EventTriggerPacketV1,
    IngestAlertPacketV1,
    SourceArtifactPacketV1,
    deterministic_packet_id,
)
from agentic_harness.contracts.queues_v1 import QueueJobV1, deterministic_job_id
from agentic_harness.store.protocol import HarnessStoreProtocol, StoreError


SOURCE_FAMILY_TRANSCRIPTS = "earnings_transcript"


# ---------------------------------------------------------------------------
# Inputs injectable for tests. In production these are wired to the Supabase
# registry reader and the real transcripts ingest function.
# ---------------------------------------------------------------------------


StaleAssetProvider = Callable[[HarnessStoreProtocol, str], list[dict[str, Any]]]
"""(store, now_iso) -> [{asset_id, last_fetched_at_utc, expected_freshness_hours, ...}]"""

TranscriptFetcher = Callable[[dict[str, Any]], dict[str, Any]]
"""(job_meta) -> fetch result. Must return {ok: bool, transcript_ref, ...} or raise."""


_STALE_ASSET_PROVIDER: Optional[StaleAssetProvider] = None
_TRANSCRIPT_FETCHER: Optional[TranscriptFetcher] = None


def set_stale_asset_provider(fn: Optional[StaleAssetProvider]) -> None:
    global _STALE_ASSET_PROVIDER
    _STALE_ASSET_PROVIDER = fn


def set_transcript_fetcher(fn: Optional[TranscriptFetcher]) -> None:
    global _TRANSCRIPT_FETCHER
    _TRANSCRIPT_FETCHER = fn


def _fallback_stale_asset_provider(
    store: HarnessStoreProtocol, now_iso: str
) -> list[dict[str, Any]]:
    """Default: nothing is considered stale. Operators override this in
    production by calling ``set_stale_asset_provider`` at app startup."""

    return []


def _fallback_transcript_fetcher(job_meta: dict[str, Any]) -> dict[str, Any]:
    """Deterministic default: refuse the fetch with a clear error.

    This keeps the harness network-free until an operator wires the real
    transcript ingest path. The scheduler treats this as a normal job
    failure and sends it to DLQ after ``max_attempts``.
    """

    return {
        "ok": False,
        "error": "transcript_fetcher_not_configured",
    }


# ---------------------------------------------------------------------------
# Source Scout / Event Trigger / Ingest Coordinator
# ---------------------------------------------------------------------------


def _freshness_hours_exceeded(
    *, last_fetched_at_utc: Optional[str], expected_freshness_hours: int, now_iso: str
) -> bool:
    if not last_fetched_at_utc:
        return True
    try:
        last = datetime.fromisoformat(str(last_fetched_at_utc).replace("Z", "+00:00"))
        now = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - last) >= timedelta(hours=max(1, int(expected_freshness_hours)))


def source_scout_agent(store: HarnessStoreProtocol, now_iso: str) -> list[dict[str, Any]]:
    provider = _STALE_ASSET_PROVIDER or _fallback_stale_asset_provider
    candidates = provider(store, now_iso)
    if not isinstance(candidates, list):
        return []
    stale: list[dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        fh = int(c.get("expected_freshness_hours") or 72)
        if _freshness_hours_exceeded(
            last_fetched_at_utc=str(c.get("last_fetched_at_utc") or ""),
            expected_freshness_hours=fh,
            now_iso=now_iso,
        ):
            stale.append({**c, "expected_freshness_hours": fh})
    return stale


def event_trigger_agent(
    *, candidate: dict[str, Any], now_iso: str
) -> EventTriggerPacketV1:
    asset_id = str(candidate["asset_id"]).strip().upper()
    fh = int(candidate.get("expected_freshness_hours") or 72)
    provenance = list(candidate.get("provenance_refs") or [f"registry://today/{asset_id}"])
    pid = deterministic_packet_id(
        packet_type="EventTriggerPacketV1",
        created_by_agent="event_trigger_agent",
        target_scope={"asset_id": asset_id, "source_family": SOURCE_FAMILY_TRANSCRIPTS},
        salt=now_iso,
    )
    return EventTriggerPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "EventTriggerPacketV1",
            "target_layer": "layer1_ingest",
            "created_by_agent": "event_trigger_agent",
            "target_scope": {
                "asset_id": asset_id,
                "source_family": SOURCE_FAMILY_TRANSCRIPTS,
            },
            "provenance_refs": provenance,
            "confidence": 0.6,
            "payload": {
                "trigger_kind": "earnings_transcript_stale",
                "asset_id": asset_id,
                "expected_freshness_hours": fh,
                "last_fetched_at_utc": str(candidate.get("last_fetched_at_utc") or ""),
            },
            "expiry_or_recheck_rule": f"recheck_after_{fh}h",
        }
    )


def ingest_coordinator_agent(
    *,
    store: HarnessStoreProtocol,
    trigger: EventTriggerPacketV1,
    now_iso: str,
) -> Optional[dict[str, Any]]:
    asset_id = str(trigger.payload.get("asset_id") or "").upper()
    fh = int(trigger.payload.get("expected_freshness_hours") or 72)
    pid = deterministic_packet_id(
        packet_type="IngestAlertPacketV1",
        created_by_agent="ingest_coordinator_agent",
        target_scope={"asset_id": asset_id, "source_family": SOURCE_FAMILY_TRANSCRIPTS},
        salt=str(trigger.packet_id),
    )
    alert = IngestAlertPacketV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "IngestAlertPacketV1",
            "target_layer": "layer1_ingest",
            "created_by_agent": "ingest_coordinator_agent",
            "target_scope": {
                "asset_id": asset_id,
                "source_family": SOURCE_FAMILY_TRANSCRIPTS,
            },
            "provenance_refs": list(trigger.provenance_refs)
            + [f"packet:{trigger.packet_id}"],
            "confidence": 0.7,
            "payload": {
                "source_family": SOURCE_FAMILY_TRANSCRIPTS,
                "trigger_kind": "earnings_transcript_stale",
                "asset_ids": [asset_id],
                "expected_freshness_hours": fh,
                "triggering_packet_id": trigger.packet_id,
            },
            "status": "enqueued",
            "expiry_or_recheck_rule": f"recheck_after_{fh}h",
        }
    )
    store.upsert_packet(trigger.model_dump())
    store.upsert_packet(alert.model_dump())
    job = QueueJobV1.model_validate(
        {
            "job_id": deterministic_job_id(
                queue_class="ingest_queue",
                packet_id=alert.packet_id,
                salt=now_iso,
            ),
            "queue_class": "ingest_queue",
            "packet_id": alert.packet_id,
            "not_before_utc": now_iso,
            "worker_agent": "transcripts_adapter_worker",
        }
    )
    try:
        store.enqueue_job(job.model_dump())
    except StoreError:
        return None
    return {
        "trigger_packet_id": trigger.packet_id,
        "alert_packet_id": alert.packet_id,
        "job_id": job.job_id,
    }


def propose_layer1_cadence(
    store: HarnessStoreProtocol, now_iso: str
) -> dict[str, Any]:
    stale = source_scout_agent(store, now_iso)
    triggered = 0
    enqueued = 0
    for c in stale:
        try:
            trigger = event_trigger_agent(candidate=c, now_iso=now_iso)
        except Exception:
            continue
        triggered += 1
        res = ingest_coordinator_agent(store=store, trigger=trigger, now_iso=now_iso)
        if res is not None:
            enqueued += 1
    return {"stale_asset_count": len(stale), "triggered": triggered, "enqueued": enqueued}


# ---------------------------------------------------------------------------
# Queue worker
# ---------------------------------------------------------------------------


def ingest_queue_worker(
    store: HarnessStoreProtocol, job_row: dict[str, Any]
) -> dict[str, Any]:
    alert_packet_id = str(job_row.get("packet_id") or "")
    alert = store.get_packet(alert_packet_id)
    if alert is None:
        return {"ok": False, "error": f"alert_packet_missing: {alert_packet_id}"}
    payload = dict(alert.get("payload") or {})
    asset_id = (list(payload.get("asset_ids") or []) or [""])[0]
    fetcher = _TRANSCRIPT_FETCHER or _fallback_transcript_fetcher
    try:
        res = fetcher(
            {
                "asset_id": asset_id,
                "source_family": payload.get("source_family"),
                "alert_packet_id": alert_packet_id,
            }
        )
    except Exception as e:
        return {"ok": False, "error": f"fetcher_exception: {e}"}
    if not isinstance(res, dict):
        return {"ok": False, "error": "fetcher_result_not_dict"}
    if not res.get("ok", False):
        return {"ok": False, "error": str(res.get("error") or "fetch_failed")}

    # Record a SourceArtifactPacketV1 as evidence the fetch succeeded.
    sa = SourceArtifactPacketV1.model_validate(
        {
            "packet_id": deterministic_packet_id(
                packet_type="SourceArtifactPacketV1",
                created_by_agent="transcripts_adapter_worker",
                target_scope={"asset_id": asset_id, "alert_packet_id": alert_packet_id},
            ),
            "packet_type": "SourceArtifactPacketV1",
            "target_layer": "layer1_ingest",
            "created_by_agent": "transcripts_adapter_worker",
            "target_scope": {
                "asset_id": asset_id,
                "alert_packet_id": alert_packet_id,
            },
            "provenance_refs": list(res.get("provenance_refs") or [f"packet:{alert_packet_id}"]),
            "confidence": float(res.get("confidence", 0.9)),
            "status": "done",
            "payload": {
                "source_family": payload.get("source_family") or SOURCE_FAMILY_TRANSCRIPTS,
                "artifact_kind": str(res.get("artifact_kind") or "transcript_text"),
                "fetch_outcome": "ok",
                "artifact_ref": str(res.get("artifact_ref") or ""),
                "fetched_at_utc": str(res.get("fetched_at_utc") or ""),
            },
        }
    )
    store.upsert_packet(sa.model_dump())
    store.set_packet_status(alert_packet_id, "done")
    return {
        "ok": True,
        "source_artifact_packet_id": sa.packet_id,
        "asset_id": asset_id,
    }
