"""Phase 47d — thick-slice Home feed + shell metadata bundle (no HTTP)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase47_runtime.home_feed import phase47d_bundle_core


def run_phase47d_thick_slice_home_feed(
    *,
    design_source_path: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    design = Path(design_source_path)
    if not design.is_absolute():
        design = (root / design).resolve()
    else:
        design = design.resolve()
    return phase47d_bundle_core(design_source_path=str(design))
