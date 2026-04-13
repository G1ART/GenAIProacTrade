"""Phase 47b — user-first UX metadata bundle (no HTTP)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase47_runtime.ui_copy import (
    ACTION_FRAMING_EXAMPLES,
    ADVANCED_BOUNDARY_RULES,
    OBJECT_HIERARCHY,
    PRIMARY_NAVIGATION,
    STATUS_TRANSLATIONS,
    navigation_contract,
)


def run_phase47b_user_first_ux(
    *,
    design_source_path: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    design = Path(design_source_path)
    if not design.is_absolute():
        design = (root / design).resolve()
    gen = datetime.now(timezone.utc).isoformat()
    examples = [{"from": k, "to": v} for k, v in sorted(STATUS_TRANSLATIONS.items())]
    nav = navigation_contract()
    return {
        "ok": True,
        "phase": "phase47b_user_first_ux",
        "generated_utc": gen,
        "design_source_path": str(design),
        "primary_navigation": PRIMARY_NAVIGATION,
        "object_hierarchy": OBJECT_HIERARCHY,
        "object_detail_sections": nav["object_detail_sections"],
        "internal_layers_retired_from_top_nav": nav["internal_layers"],
        "status_translation_examples": examples,
        "action_framing_examples": ACTION_FRAMING_EXAMPLES,
        "advanced_boundary_rules": ADVANCED_BOUNDARY_RULES,
        "phase47c": {
            "phase47c_recommendation": (
                "visual_system_spacing_typography_empty_states_and_card_rhythm_v1"
            ),
            "focus": "Phase 47c: visual system, spacing, typography, dashboard clarity, badges, empty states",
        },
    }
