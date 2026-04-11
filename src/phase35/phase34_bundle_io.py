"""Phase 34 클로즈아웃 번들에서 동기화·미성숙 행 추출."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_phase34_bundle(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def synchronized_rows_from_phase34(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    pgf = bundle.get("propagation_gap_final") or {}
    return [
        dict(r)
        for r in (pgf.get("rows") or [])
        if str(r.get("classification") or "") == "synchronized"
    ]


def immature_gap_rows_from_phase34(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    pgf = bundle.get("propagation_gap_final") or {}
    return [
        dict(r)
        for r in (pgf.get("rows") or [])
        if str(r.get("classification") or "")
        == "forward_not_present_window_not_matured"
    ]
