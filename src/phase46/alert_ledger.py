"""File-backed alert ledger (v1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALERT_STATUSES = frozenset(
    {"open", "acknowledged", "resolved", "superseded", "dismissed"},
)


def default_ledger_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "product_surface" / "alert_ledger_v1.json"


def load_alert_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "alerts": []}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def save_alert_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_alert(
    path: Path,
    *,
    asset_id: str,
    alert_class: str,
    message_summary: str,
    triggering_source_artifact: str,
    requires_attention: bool,
    status: str = "open",
) -> dict[str, Any]:
    ledger = load_alert_ledger(path)
    alerts = list(ledger.get("alerts") or [])
    if status not in ALERT_STATUSES:
        raise ValueError(f"invalid alert status: {status}")
    entry = {
        "alert_id": str(uuid.uuid4()),
        "alert_timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id,
        "alert_class": alert_class,
        "message_summary": message_summary,
        "triggering_source_artifact": triggering_source_artifact,
        "requires_attention": requires_attention,
        "status": status,
    }
    alerts.append(entry)
    ledger["alerts"] = alerts
    save_alert_ledger(path, ledger)
    return entry


def list_alerts(path: Path) -> list[dict[str, Any]]:
    return list(load_alert_ledger(path).get("alerts") or [])


def ensure_alert_ids(path: Path) -> bool:
    """Assign alert_id to legacy entries missing it; persist if changed."""
    ledger = load_alert_ledger(path)
    alerts = list(ledger.get("alerts") or [])
    changed = False
    for a in alerts:
        if not a.get("alert_id"):
            a["alert_id"] = str(uuid.uuid4())
            changed = True
    if changed:
        ledger["alerts"] = alerts
        save_alert_ledger(path, ledger)
    return changed


def update_alert_status(
    path: Path,
    *,
    new_status: str,
    alert_id: str | None = None,
    index: int | None = None,
    operator_note: str | None = None,
) -> dict[str, Any]:
    if new_status not in ALERT_STATUSES:
        raise ValueError(f"invalid alert status: {new_status}")
    ensure_alert_ids(path)
    ledger = load_alert_ledger(path)
    alerts = list(ledger.get("alerts") or [])
    if alert_id:
        found = -1
        for i, a in enumerate(alerts):
            if str(a.get("alert_id") or "") == alert_id:
                found = i
                break
        if found < 0:
            raise KeyError(f"alert_id not found: {alert_id}")
        idx = found
    elif index is not None:
        if index < 0 or index >= len(alerts):
            raise IndexError(f"alert index out of range: {index}")
        idx = index
    else:
        raise ValueError("need alert_id or index")
    alerts[idx] = dict(alerts[idx])
    alerts[idx]["status"] = new_status
    alerts[idx]["status_updated_utc"] = datetime.now(timezone.utc).isoformat()
    if operator_note is not None:
        alerts[idx]["operator_note"] = str(operator_note)[:4000]
    ledger["alerts"] = alerts
    save_alert_ledger(path, ledger)
    return alerts[idx]


def alert_ledger_schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "description": "Product-surface alert ledger — file-backed v1",
        "entry_fields": {
            "alert_timestamp": "ISO-8601 UTC",
            "asset_id": "str — cohort or row id",
            "alert_class": "str — taxonomy e.g. closeout_hold, reopen_eligible, gate_deferred",
            "message_summary": "str — human-readable one-liner",
            "triggering_source_artifact": "str — path or bundle phase key",
            "requires_attention": "bool",
            "status": "open | acknowledged | resolved | superseded | dismissed",
            "alert_id": "str UUID — stable reference for UI updates",
            "status_updated_utc": "optional ISO-8601 after update",
            "operator_note": "optional str",
        },
    }
