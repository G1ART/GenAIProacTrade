"""Queue class registry and ``QueueJobV1`` Pydantic shape.

Queue classes mirror the six queues listed in METIS_Agentic_Operating_Harness_v1
sec 11.2. Each queue_class carries at most one enqueued job per packet_id at a
time (idempotency invariant enforced by the store).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


QUEUE_CLASSES = (
    "ingest_queue",
    "quality_queue",
    "research_queue",
    "governance_queue",
    "surface_action_queue",
    "replay_recompute_queue",
    # AGH v1 Patch 2: operator-approved RegistryUpdateProposalV1 jobs land here
    # and are consumed by the ``registry_patch_executor`` worker which performs
    # the atomic brain-bundle write.
    "registry_apply_queue",
    # AGH v1 Patch 5: bounded sandbox queue. Consumed by the Layer 3
    # ``sandbox_executor_v1`` worker; Patch 5 only supports the
    # ``validation_rerun`` sandbox_kind closed-loop. Separate queue class
    # (rather than reusing ``research_queue``) so DLQ + idempotency live
    # on a single purpose-built rail.
    "sandbox_queue",
)

QueueClass = Literal[
    "ingest_queue",
    "quality_queue",
    "research_queue",
    "governance_queue",
    "surface_action_queue",
    "replay_recompute_queue",
    "registry_apply_queue",
    "sandbox_queue",
]

JOB_STATUS_VALUES = ("enqueued", "running", "done", "dlq", "expired")

JobStatus = Literal["enqueued", "running", "done", "dlq", "expired"]


def deterministic_job_id(*, queue_class: str, packet_id: str, salt: str = "") -> str:
    payload = f"{queue_class}|{packet_id}|{salt}".encode("utf-8")
    return "job_" + hashlib.sha256(payload).hexdigest()[:22]


class QueueJobV1(BaseModel):
    contract: str = "METIS_AGENTIC_HARNESS_QUEUE_JOB_V1"

    job_id: str = Field(min_length=1)
    queue_class: QueueClass
    packet_id: str = Field(min_length=1)

    enqueued_at_utc: str = ""
    not_before_utc: str = ""

    attempts: int = Field(default=0, ge=0, le=99)
    max_attempts: int = Field(default=3, ge=1, le=10)

    last_error: str = ""
    status: JobStatus = "enqueued"
    worker_agent: str = ""

    result_json: Optional[dict[str, Any]] = None

    @field_validator("queue_class")
    @classmethod
    def _queue_class_vocab(cls, v: str) -> str:
        if v not in QUEUE_CLASSES:
            raise ValueError(f"queue_class must be one of {QUEUE_CLASSES}, got {v!r}")
        return v

    @field_validator("last_error", "worker_agent")
    @classmethod
    def _stringify(cls, v: Any) -> str:
        return str(v or "").strip()

    @model_validator(mode="after")
    def _stamp_times(self) -> "QueueJobV1":
        now = datetime.now(timezone.utc).isoformat()
        if not str(self.enqueued_at_utc or "").strip():
            self.enqueued_at_utc = now
        if not str(self.not_before_utc or "").strip():
            self.not_before_utc = self.enqueued_at_utc
        return self
