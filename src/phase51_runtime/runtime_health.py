"""Machine-readable runtime health summary (v1) for cockpit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase50_runtime.control_plane import default_control_plane_path, load_control_plane
from phase50_runtime.runtime_audit_log import default_audit_log_path, load_audit_log, summarize_audit_tail
from phase50_runtime.trigger_controls import trigger_controls_summary

from phase51_runtime.external_trigger_ingest import default_ingest_registry_path, load_ingest_registry


def default_runtime_health_summary_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "runtime_health_summary_v1.json"


def _classify_health(cp: dict[str, Any], last_skip_reason: str | None) -> str:
    if not cp.get("enabled", True):
        return "disabled"
    if cp.get("maintenance_mode"):
        return "maintenance"
    if last_skip_reason in ("lease_not_acquired", "timing_blocked", "max_cycles_per_window"):
        return "degraded"
    return "healthy"


def build_runtime_health_summary(
    *,
    repo_root: Path | None = None,
    control_plane_path: Path | None = None,
    audit_path: Path | None = None,
    ingest_registry_path: Path | None = None,
    last_n_audit: int = 25,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    cp_p = control_plane_path or default_control_plane_path(root)
    au_p = audit_path or default_audit_log_path(root)
    ing_p = ingest_registry_path or default_ingest_registry_path(root)

    cp = load_control_plane(cp_p)
    audit_sum = summarize_audit_tail(au_p, last_n=last_n_audit)
    last = audit_sum.get("last_entry") or {}
    last_skip = None
    if last.get("cycle_skipped"):
        last_skip = str(last.get("why_cycle_stopped") or "")

    reg = load_ingest_registry(ing_p)
    entries = list(reg.get("entries") or [])
    accepted = [e for e in entries if e.get("status") == "accepted"]
    rejected = [e for e in entries if e.get("status") == "rejected"]
    deduped = [e for e in entries if e.get("status") == "deduped"]
    consumed = [e for e in entries if e.get("status") == "consumed"]

    last_acc = next((e for e in reversed(entries) if e.get("status") == "accepted"), None)
    last_rej = next((e for e in reversed(entries) if e.get("status") == "rejected"), None)

    recent_skips: list[dict[str, Any]] = []
    log = load_audit_log(au_p)
    for e in reversed(list(log.get("entries") or [])[-15:]):
        if e.get("cycle_skipped"):
            recent_skips.append(
                {
                    "timestamp": e.get("timestamp"),
                    "why": e.get("why_cycle_stopped"),
                    "detail": (e.get("controls_applied") or {}).get("timing"),
                }
            )

    summary = {
        "schema_version": 1,
        "control_plane_excerpt": {
            "enabled": cp.get("enabled"),
            "maintenance_mode": cp.get("maintenance_mode"),
            "max_cycles_per_window": cp.get("max_cycles_per_window"),
            "window_seconds": cp.get("window_seconds"),
        },
        "trigger_controls": trigger_controls_summary(cp),
        "last_cycle_audit_excerpt": {
            "timestamp": last.get("timestamp"),
            "cycle_id": last.get("cycle_id"),
            "skipped": last.get("cycle_skipped"),
            "why_stopped": last.get("why_cycle_stopped"),
            "jobs_created": last.get("jobs_created_count"),
            "jobs_executed": last.get("jobs_executed_count"),
        },
        "audit_tail_summary": audit_sum,
        "external_ingest_counts": {
            "total_entries": len(entries),
            "accepted_pending": len([e for e in accepted if not e.get("linked_cycle_id")]),
            "consumed": len(consumed),
            "rejected": len(rejected),
            "deduped": len(deduped),
        },
        "last_accepted_trigger": (
            {
                "event_id": last_acc.get("event_id"),
                "normalized_trigger_type": last_acc.get("normalized_trigger_type"),
                "received_at": last_acc.get("received_at"),
            }
            if last_acc
            else None
        ),
        "last_rejected_trigger": (
            {
                "event_id": last_rej.get("event_id"),
                "reason": last_rej.get("accepted_or_rejected_reason"),
                "raw_event_type": last_rej.get("raw_event_type"),
            }
            if last_rej
            else None
        ),
        "recent_skip_reasons": recent_skips[:8],
        "health_status": _classify_health(cp, last_skip),
    }
    return summary


def write_runtime_health_summary(path: Path, summary: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path.resolve())


def refresh_and_persist_runtime_health(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    s = build_runtime_health_summary(repo_root=root)
    write_runtime_health_summary(default_runtime_health_summary_path(root), s)
    return s
