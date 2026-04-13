"""Phase 47c — traceability, replay grammar, counterfactual scaffold (bundle only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase47_runtime.traceability_replay import phase47c_bundle_core


def run_phase47c_traceability_replay(
    *,
    design_source_paths: list[str],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    resolved: list[str] = []
    for raw in design_source_paths:
        s = str(raw or "").strip()
        if not s:
            continue
        p = Path(s)
        if not p.is_absolute():
            p = (root / p).resolve()
        resolved.append(str(p))
    if not resolved:
        resolved = [str((root / "docs" / "DESIGN_V3_MINIMAL_AND_STRONG.md").resolve())]
    return phase47c_bundle_core(design_paths=resolved)
