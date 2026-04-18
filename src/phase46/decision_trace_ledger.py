"""File-backed founder / operator decision trace ledger (v1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISION_TYPES = frozenset(
    {
        "buy",
        "sell",
        "hold",
        "watch",
        "defer",
        "reopen_request",
        "dismiss_alert",
    }
)


def default_ledger_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "product_surface" / "decision_trace_ledger_v1.json"


def load_decision_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "decisions": []}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def save_decision_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_decision(
    path: Path,
    *,
    asset_id: str,
    decision_type: str,
    founder_note: str,
    linked_message_summary: str,
    linked_authoritative_artifact: str,
    linked_research_provenance: str,
    outcome_placeholder: str | None = None,
    replay_lineage_pointer: str | None = None,
    message_snapshot_id: str | None = None,
    linked_registry_entry_id: str | None = None,
    linked_artifact_id: str | None = None,
    brain_overlay_ids_at_decision: list[str] | None = None,
    persona_candidate_ids_at_decision: list[str] | None = None,
) -> dict[str, Any]:
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"invalid decision_type: {decision_type}")
    ledger = load_decision_ledger(path)
    decs = list(ledger.get("decisions") or [])
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id,
        "decision_type": decision_type,
        "founder_note": founder_note,
        "linked_message_summary": linked_message_summary,
        "linked_authoritative_artifact": linked_authoritative_artifact,
        "linked_research_provenance": linked_research_provenance,
        "outcome_placeholder": outcome_placeholder,
    }
    if replay_lineage_pointer is not None:
        entry["replay_lineage_pointer"] = str(replay_lineage_pointer)[:2000]
    if message_snapshot_id is not None:
        entry["message_snapshot_id"] = str(message_snapshot_id)[:2000]
    if linked_registry_entry_id is not None:
        entry["linked_registry_entry_id"] = str(linked_registry_entry_id)[:2000]
    if linked_artifact_id is not None:
        entry["linked_artifact_id"] = str(linked_artifact_id)[:2000]
    if brain_overlay_ids_at_decision is not None:
        entry["brain_overlay_ids_at_decision"] = [
            str(x) for x in list(brain_overlay_ids_at_decision or []) if str(x).strip()
        ]
    if persona_candidate_ids_at_decision is not None:
        entry["persona_candidate_ids_at_decision"] = [
            str(x) for x in list(persona_candidate_ids_at_decision or []) if str(x).strip()
        ]
    decs.append(entry)
    ledger["decisions"] = decs
    save_decision_ledger(path, ledger)
    return entry


def list_decisions(path: Path) -> list[dict[str, Any]]:
    return list(load_decision_ledger(path).get("decisions") or [])


def decision_trace_ledger_schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "description": "Founder/operator decision trace — why, not only what the engine said",
        "entry_fields": {
            "timestamp": "ISO-8601 UTC",
            "asset_id": "str",
            "decision_type": f"one of {sorted(DECISION_TYPES)}",
            "founder_note": "str",
            "linked_message_summary": "str",
            "linked_authoritative_artifact": "str — path or id",
            "linked_research_provenance": "str",
            "outcome_placeholder": "optional str for future outcome linkage",
            "replay_lineage_pointer": "optional — registry lineage key (Product Spec §6.3 replay_lineage_pointer)",
            "message_snapshot_id": "optional — deterministic message row snapshot id (Patch Bundle C)",
            "linked_registry_entry_id": "optional — Active Horizon Registry entry id at decision time",
            "linked_artifact_id": "optional — active artifact id at decision time",
            "brain_overlay_ids_at_decision": (
                "optional list[str] — brain_overlays_v1 ids influencing the active "
                "registry entry at decision time (Pragmatic Brain Absorption v1 §8.3)"
            ),
            "persona_candidate_ids_at_decision": (
                "optional list[str] — PersonaCandidatePacketV1 ids considered at "
                "decision time. Candidate-only; presence never implies promotion."
            ),
        },
    }
