"""Optional JSON preset for universe / output stem (operator profile)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_preset_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / ".operator_closeout_preset.json"


def load_operator_closeout_preset(path: Path | None = None) -> dict[str, Any]:
    p = path or default_preset_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
