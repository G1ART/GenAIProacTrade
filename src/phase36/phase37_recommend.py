"""Phase 37 진입 권고 — freeze 판정에 정렬."""

from __future__ import annotations

from typing import Any

from phase36.substrate_freeze_readiness import (
    FREEZE_PUBLIC_CORE,
    ONE_MORE_NARROW,
    STILL_BLOCKED,
)


def recommend_phase37_after_phase36(
    *,
    freeze_report: dict[str, Any],
) -> dict[str, Any]:
    rec = str(freeze_report.get("substrate_freeze_recommendation") or "")
    if rec == STILL_BLOCKED:
        return {
            "phase37_recommendation": "stabilize_structural_substrate_before_research_engine",
            "rationale": "Freeze assessment returned high-impact structural concern; do not shift primary build upward yet.",
        }
    if rec == ONE_MORE_NARROW:
        return {
            "phase37_recommendation": "complete_narrow_integrity_round_then_execute_research_handoff",
            "rationale": "Residual metadata or repairable state_change seams remain; finish bounded closure then export handoff.",
        }
    return {
        "phase37_recommendation": "execute_research_engine_backlog_sprint",
        "rationale": "Public-core substrate sufficient for MVP freeze; primary energy to hypothesis forge, PIT lab, promotion gate, casebook, explanation layer.",
    }
