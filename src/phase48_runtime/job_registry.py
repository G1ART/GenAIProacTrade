"""Persistent research job registry (file-backed v1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase48_runtime.budget_policy import BUDGET_CLASSES

JOB_STATUSES = frozenset({"pending", "running", "completed", "blocked", "cancelled"})

JOB_TYPES = frozenset(
    {
        "evidence.refresh",
        "hypothesis.check",
        "debate.execute",
        "premium.escalation_candidate",
        "discovery.publish_candidate",
    },
)


def default_registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "research_job_registry_v1.json"


def load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": 1,
            "metadata": {"last_phase46_generated_utc": None, "last_cycle_utc": None},
            "jobs": [],
        }
    return dict(json.loads(path.read_text(encoding="utf-8")))


def save_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_pending_dedupe(registry: dict[str, Any], dedupe_key: str) -> dict[str, Any] | None:
    for j in registry.get("jobs") or []:
        if j.get("dedupe_key") == dedupe_key and j.get("status") in ("pending", "running"):
            return j
    return None


def job_with_dedupe_exists(registry: dict[str, Any], dedupe_key: str) -> bool:
    for j in registry.get("jobs") or []:
        if j.get("dedupe_key") == dedupe_key:
            return True
    return False


def append_job(
    path: Path,
    *,
    job_type: str,
    asset_scope: dict[str, Any],
    trigger_source: str,
    priority: int,
    budget_class: str,
    dedupe_key: str,
    trigger_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if job_type not in JOB_TYPES:
        raise ValueError(f"invalid job_type: {job_type}")
    if budget_class not in BUDGET_CLASSES:
        raise ValueError(f"invalid budget_class: {budget_class}")
    reg = load_registry(path)
    jobs = list(reg.get("jobs") or [])
    job = {
        "job_id": str(uuid.uuid4()),
        "job_type": job_type,
        "asset_scope": asset_scope,
        "trigger_source": trigger_source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "priority": priority,
        "budget_class": budget_class,
        "attempt_count": 0,
        "result_summary": "",
        "output_artifacts": [],
        "dedupe_key": dedupe_key,
        "trigger_payload": trigger_payload or {},
    }
    jobs.append(job)
    reg["jobs"] = jobs
    save_registry(path, reg)
    return job


def update_job(
    path: Path,
    job_id: str,
    *,
    status: str | None = None,
    result_summary: str | None = None,
    output_artifacts: list[Any] | None = None,
    increment_attempt: bool = False,
) -> dict[str, Any]:
    reg = load_registry(path)
    jobs = list(reg.get("jobs") or [])
    found = None
    for i, j in enumerate(jobs):
        if j.get("job_id") == job_id:
            found = i
            break
    if found is None:
        raise KeyError(job_id)
    j = dict(jobs[found])
    if status is not None:
        if status not in JOB_STATUSES:
            raise ValueError(f"invalid status: {status}")
        j["status"] = status
    if result_summary is not None:
        j["result_summary"] = result_summary
    if output_artifacts is not None:
        j["output_artifacts"] = output_artifacts
    if increment_attempt:
        j["attempt_count"] = int(j.get("attempt_count") or 0) + 1
    jobs[found] = j
    reg["jobs"] = jobs
    save_registry(path, reg)
    return j


def update_metadata(path: Path, **kwargs: Any) -> None:
    reg = load_registry(path)
    meta = dict(reg.get("metadata") or {})
    meta.update(kwargs)
    reg["metadata"] = meta
    save_registry(path, reg)
