"""Research re-run readiness from program + substrate snapshot."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from public_depth.constants import READINESS_JOINED_MULTIPLIER
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.constants import MIN_SAMPLE_ROWS


def build_research_readiness_summary(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    universe = str(prog.get("universe_name") or "")
    metrics, _ex = compute_substrate_coverage(client, universe_name=universe)
    joined = int(metrics.get("joined_recipe_substrate_row_count") or 0)
    threshold = MIN_SAMPLE_ROWS * READINESS_JOINED_MULTIPLIER
    thin = metrics.get("thin_input_share")
    qctx = prog.get("linked_quality_context_json")
    qctx_d = qctx if isinstance(qctx, dict) else {}
    program_quality_hint = str(qctx_d.get("quality_class") or "")

    recommend_rerun_p15_p16 = joined >= threshold and (
        thin is None or (isinstance(thin, (int, float)) and thin < 0.55)
    )
    escalate_premium = False

    return {
        "ok": True,
        "program_id": program_id,
        "universe_name": universe,
        "program_quality_context_hint": program_quality_hint or None,
        "substrate_snapshot": metrics,
        "thresholds": {
            "min_sample_rows": MIN_SAMPLE_ROWS,
            "readiness_joined_threshold": threshold,
        },
        "recommend_rerun_phase_15_16": recommend_rerun_p15_p16,
        "recommend_escalate_premium_seam": escalate_premium,
        "notes": (
            "joined_recipe_substrate_row_count가 임계 이상이고 thin_input_share가 완화된 경우 "
            "Phase 15/16 재실행을 권고. 그렇지 않으면 공개 기판 추가 확장을 우선."
        ),
    }
