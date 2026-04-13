"""Bounded adapters: file drop, JSON body (CLI / HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase50_runtime.control_plane import load_control_plane

from phase51_runtime.external_trigger_audit import audit_ingest_outcome
from phase51_runtime.external_trigger_ingest import default_ingest_registry_path, ingest_external_event
from phase51_runtime.trigger_normalizer import normalize_raw_event


def load_events_from_file(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if "events" in raw and isinstance(raw["events"], list):
            return [x for x in raw["events"] if isinstance(x, dict)]
        return [raw]
    return []


def process_external_payload(
    body: dict[str, Any],
    *,
    repo_root: Path,
    ingest_registry_path: Path | None = None,
    audit_path: Path | None = None,
    control_plane_path: Path | None = None,
    maintenance_blocks_accept: bool = False,
) -> dict[str, Any]:
    """Single event object -> registry row + audit."""
    from phase51_runtime.external_trigger_audit import default_external_trigger_audit_path
    from phase50_runtime.control_plane import default_control_plane_path

    ip = ingest_registry_path or default_ingest_registry_path(repo_root)
    ap = audit_path or default_external_trigger_audit_path(repo_root)
    cp_path = control_plane_path or default_control_plane_path(repo_root)
    cp = load_control_plane(cp_path)

    norm_pre = normalize_raw_event(body)
    norm_ok = bool(norm_pre.get("ok"))
    norm_reason = None if norm_ok else str(norm_pre.get("reason"))

    entry = ingest_external_event(
        body,
        ingest_registry_path=ip,
        control_plane=cp,
        maintenance_blocks_accept=maintenance_blocks_accept,
    )
    deduped = entry.get("status") == "deduped"
    audit_ingest_outcome(
        ap,
        raw_event=body,
        registry_entry=entry,
        normalization_ok=norm_ok,
        normalization_reason=norm_reason,
        deduped=deduped,
        consumed_by_cycle_id=None,
    )
    return {"ok": True, "registry_entry": entry, "ingest_registry_path": str(ip), "audit_path": str(ap)}


def process_events_from_file(
    path: Path,
    *,
    repo_root: Path,
    ingest_registry_path: Path | None = None,
    audit_path: Path | None = None,
    control_plane_path: Path | None = None,
    maintenance_blocks_accept: bool = False,
) -> list[dict[str, Any]]:
    out = []
    for ev in load_events_from_file(path):
        out.append(
            process_external_payload(
                ev,
                repo_root=repo_root,
                ingest_registry_path=ingest_registry_path,
                audit_path=audit_path,
                control_plane_path=control_plane_path,
                maintenance_blocks_accept=maintenance_blocks_accept,
            )
        )
    return out
