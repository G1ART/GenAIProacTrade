"""Slice B — persisted message snapshot → governed Ask / sandbox safe context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metis_brain.message_snapshots_store import get_message_snapshot


def _clip(v: object) -> str:
    t = str(v or "").strip().replace("\n", " ")
    return t[:500] if t else ""


def snapshot_record_to_copilot_context(record: dict[str, Any]) -> dict[str, str]:
    """Map snapshot store record to keys accepted by ``process_governed_prompt`` sanitization."""
    msg = record.get("message") if isinstance(record.get("message"), dict) else {}
    rj = record.get("replay_lineage_join_v1") if isinstance(record.get("replay_lineage_join_v1"), dict) else {}
    sp = record.get("spectrum") if isinstance(record.get("spectrum"), dict) else {}

    out: dict[str, str] = {}
    pairs = [
        ("asset_id", record.get("asset_id")),
        ("horizon", record.get("horizon")),
        ("active_model_family", record.get("active_model_family")),
        ("as_of_utc", record.get("as_of_utc")),
        ("headline", msg.get("headline")),
        ("message_summary", msg.get("one_line_take") or msg.get("headline")),
        ("why_now", msg.get("why_now")),
        ("what_to_watch", msg.get("what_to_watch")),
        ("what_remains_unproven", msg.get("what_remains_unproven")),
        ("linked_registry_entry_id", msg.get("linked_registry_entry_id") or rj.get("linked_registry_entry_id")),
        ("linked_artifact_id", msg.get("linked_artifact_id") or rj.get("linked_artifact_id")),
        ("replay_lineage_pointer", rj.get("replay_lineage_pointer")),
        ("message_snapshot_id", rj.get("message_snapshot_id")),
        ("spectrum_band", sp.get("spectrum_band")),
        ("spectrum_quintile", sp.get("spectrum_quintile")),
        ("spectrum_position", sp.get("spectrum_position")),
        ("rank_index", sp.get("rank_index")),
        ("rank_movement", sp.get("rank_movement")),
    ]
    for k, v in pairs:
        c = _clip(v)
        if c:
            out[k] = c
    if out:
        out.setdefault("source", "message_snapshot")
    return out


def enrich_copilot_context_from_message_snapshot(
    repo_root: Path,
    snapshot_id: str,
    base: dict[str, Any] | None,
) -> tuple[dict[str, str], str | None]:
    """Merge ``base`` copilot_context with snapshot-derived fields (base wins when non-empty)."""
    sid = (snapshot_id or "").strip()
    if not sid:
        return {}, "snapshot_id_required"
    snap = get_message_snapshot(repo_root, sid)
    if not snap:
        return {}, "snapshot_not_found"
    fills = snapshot_record_to_copilot_context(snap)
    out: dict[str, str] = {}
    base_d = base if isinstance(base, dict) else {}
    for k, v in base_d.items():
        if not isinstance(k, str):
            continue
        c = _clip(v)
        if c:
            out[k.strip()[:64]] = c
    for k, v in fills.items():
        if k not in out or not out[k].strip():
            out[k] = v
    out["message_snapshot_id"] = sid[:500]
    return out, None
