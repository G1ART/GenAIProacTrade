"""Explicit Phase 15 / Phase 16 rerun trigger booleans (machine-readable)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from public_buildout.constants import (
    JOINED_THRESHOLD_PHASE15,
    JOINED_THRESHOLD_PHASE16,
    THIN_SHARE_MAX_PHASE15,
    THIN_SHARE_MAX_PHASE16,
)
from public_depth.diagnostics import compute_substrate_coverage


def build_revalidation_trigger(client: Any, *, program_id: str) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    universe = str(prog.get("universe_name") or "")
    metrics, _ex = compute_substrate_coverage(client, universe_name=universe)
    joined = int(metrics.get("joined_recipe_substrate_row_count") or 0)
    thin = metrics.get("thin_input_share")
    qctx = prog.get("linked_quality_context_json")
    qctx_d = qctx if isinstance(qctx, dict) else {}

    def _thin_ok(max_share: float) -> bool:
        if thin is None:
            return True
        if isinstance(thin, (int, float)):
            return float(thin) < max_share
        return False

    r15 = joined >= JOINED_THRESHOLD_PHASE15 and _thin_ok(THIN_SHARE_MAX_PHASE15)
    r16 = joined >= JOINED_THRESHOLD_PHASE16 and _thin_ok(THIN_SHARE_MAX_PHASE16)

    return {
        "ok": True,
        "program_id": program_id,
        "universe_name": universe,
        "program_quality_context_hint": str(qctx_d.get("quality_class") or "") or None,
        "substrate_snapshot": metrics,
        "thresholds": {
            "joined_phase15": JOINED_THRESHOLD_PHASE15,
            "joined_phase16": JOINED_THRESHOLD_PHASE16,
            "thin_share_max_phase15": THIN_SHARE_MAX_PHASE15,
            "thin_share_max_phase16": THIN_SHARE_MAX_PHASE16,
        },
        "recommend_rerun_phase15": r15,
        "recommend_rerun_phase16": r16,
        "notes": (
            "Phase 15 권고: joined_recipe_substrate_row_count >= joined_phase15 이고 "
            "thin_input_share < thin_share_max_phase15. "
            "Phase 16은 joined·thin 바가 더 엄격함."
        ),
    }
