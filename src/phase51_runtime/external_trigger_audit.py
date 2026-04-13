"""Audit trail for external trigger ingest (separate from cycle audit)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_external_trigger_audit_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_trigger_audit_log_v1.json"


def load_external_audit(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "entries": []}


def append_external_audit(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    log = load_external_audit(path)
    rows = list(log.get("entries") or [])
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    rows.append(row)
    log["entries"] = rows
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return row


def audit_ingest_outcome(
    path: Path,
    *,
    raw_event: dict[str, Any],
    registry_entry: dict[str, Any],
    normalization_ok: bool,
    normalization_reason: str | None,
    deduped: bool,
    consumed_by_cycle_id: str | None,
) -> dict[str, Any]:
    return append_external_audit(
        path,
        {
            "kind": "external_ingest",
            "raw_event_excerpt": {
                "source_type": raw_event.get("source_type"),
                "source_id": raw_event.get("source_id"),
                "raw_event_type": raw_event.get("raw_event_type"),
            },
            "event_id": registry_entry.get("event_id"),
            "registry_status": registry_entry.get("status"),
            "accepted_or_rejected_reason": registry_entry.get("accepted_or_rejected_reason"),
            "normalized_trigger_type": registry_entry.get("normalized_trigger_type"),
            "normalization_ok": normalization_ok,
            "normalization_reason": normalization_reason,
            "deduped_away": deduped,
            "consumed_by_cycle_id": consumed_by_cycle_id,
        },
    )
