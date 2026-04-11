"""Write canonical JSON artifacts under data/research_engine/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_research_data_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, payload: list[Any] | dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return str(path.resolve())
