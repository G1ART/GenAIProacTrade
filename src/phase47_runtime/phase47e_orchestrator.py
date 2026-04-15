"""Phase 47e — bilingual user language (KO/EN) contract bundle (no HTTP)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase47_runtime.home_feed import phase47d_bundle_core
from phase47_runtime.phase47e_user_locale import SUPPORTED_LANGS, export_shell_locale_dict
from phase47_runtime.ui_copy import navigation_contract


def run_phase47e_bilingual_user_language(
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
    gen = datetime.now(timezone.utc).isoformat()
    core = phase47d_bundle_core(design_source_path=str(design))
    locale_snapshots = {lg: export_shell_locale_dict(lg) for lg in SUPPORTED_LANGS}
    nav_samples = {lg: navigation_contract(lg)["primary_navigation"][:3] for lg in SUPPORTED_LANGS}
    return {
        "ok": True,
        "phase": "phase47e_bilingual_user_language",
        "generated_utc": gen,
        "design_source_path": str(design),
        "shell_version": "phase47e",
        "supported_langs": list(SUPPORTED_LANGS),
        "locale_string_counts": {lg: len(locale_snapshots[lg]) for lg in SUPPORTED_LANGS},
        "navigation_primary_nav_sample": nav_samples,
        "phase47d_core_phase": core.get("phase"),
        "phase47f": core.get("phase47f"),
    }
