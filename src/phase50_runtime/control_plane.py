"""Persistent runtime control plane registry (v1)."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED = [
    "changed_artifact_bundle",
    "operator_research_signal",
    "closeout_reopen_candidate",
    "named_source_signal",
    "manual_watchlist",
]


def default_control_plane_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": True,
        "maintenance_mode": False,
        "max_concurrent_cycles": 1,
        "default_cycle_profile": "low_cost_polling",
        "allowed_trigger_types": list(DEFAULT_ALLOWED),
        "disabled_trigger_types": [],
        "max_cycles_per_window": 120,
        "window_seconds": 3600,
        "last_operator_override_at": None,
        "operator_note": "",
        "positive_path_smoke_enabled": False,
        "legacy_external_ingest_enabled": False,
    }


def default_control_plane_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "runtime_control_plane_v1.json"


def load_control_plane(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return default_control_plane_state()
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = default_control_plane_state()
    base.update({k: v for k, v in raw.items() if k in base})
    return base


def save_control_plane(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    to_write = default_control_plane_state()
    to_write.update({k: state[k] for k in to_write if k in state})
    path.write_text(json.dumps(to_write, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_control_plane_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        st = default_control_plane_state()
        save_control_plane(path, st)
        return st
    return load_control_plane(path)


def record_operator_override(path: Path, *, note: str) -> dict[str, Any]:
    st = load_control_plane(path)
    st["last_operator_override_at"] = datetime.now(timezone.utc).isoformat()
    st["operator_note"] = str(note)[:2000]
    save_control_plane(path, st)
    return deepcopy(st)
