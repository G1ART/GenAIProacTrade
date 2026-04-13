"""Append-only runtime audit log for proactive research cycles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_audit_log_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "runtime_audit_log_v1.json"


def load_audit_log(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "entries": []}


def append_audit_entry(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    log = load_audit_log(path)
    rows = list(log.get("entries") or [])
    rows.append(entry)
    log["entries"] = rows
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def build_audit_entry(
    *,
    cycle_id: str,
    why_started: str,
    lease_acquired: bool,
    controls_applied: dict[str, Any],
    triggers_evaluated: int,
    jobs_created: int,
    jobs_executed: int,
    why_stopped: str,
    skipped: bool,
    operator_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "why_cycle_started": why_started,
        "lease_acquired": lease_acquired,
        "controls_applied": controls_applied,
        "triggers_evaluated_count": triggers_evaluated,
        "jobs_created_count": jobs_created,
        "jobs_executed_count": jobs_executed,
        "why_cycle_stopped": why_stopped,
        "cycle_skipped": skipped,
        "operator_override": operator_override,
    }


def summarize_audit_tail(path: Path, *, last_n: int = 30) -> dict[str, Any]:
    log = load_audit_log(path)
    entries = list(log.get("entries") or [])
    tail = entries[-last_n:]
    skipped = sum(1 for e in tail if e.get("cycle_skipped"))
    return {
        "total_entries": len(entries),
        "tail_count": len(tail),
        "skipped_in_tail": skipped,
        "last_entry": tail[-1] if tail else None,
    }


def count_cycles_started_in_window(path: Path, *, window_seconds: int, now_utc: datetime | None = None) -> int:
    now = now_utc or datetime.now(timezone.utc)
    log = load_audit_log(path)
    entries = list(log.get("entries") or [])
    if window_seconds <= 0:
        return len(entries)
    n = 0
    for e in reversed(entries):
        if e.get("cycle_skipped"):
            continue
        if e.get("lease_acquired") is False:
            continue
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - t).total_seconds() <= window_seconds:
            n += 1
        else:
            break
    return n


def last_cycle_timestamp(path: Path) -> str | None:
    log = load_audit_log(path)
    entries = list(log.get("entries") or [])
    for e in reversed(entries):
        if e.get("cycle_skipped"):
            continue
        ts = e.get("timestamp")
        if ts:
            return str(ts)
    return None
