"""Persistent external source registry (auth + routing caps)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_external_source_registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_source_registry_v1.json"


def load_source_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "sources": []}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "sources": []}


def save_source_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_source_by_id(registry: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    sid = str(source_id or "").strip()
    for s in registry.get("sources") or []:
        if str(s.get("source_id") or "").strip() == sid:
            return s
    return None
