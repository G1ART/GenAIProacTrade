"""Phase 36-D: 연구 엔진·상위 레이어용 handoff 시드."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_research_engine_handoff_brief(
    *,
    universe_name: str,
    closeout_summary: dict[str, Any],
    substrate_freeze_recommendation: str,
    phase37_recommendation: str,
    residual_join_summary: dict[str, Any] | None = None,
    metadata_reconciliation_summary: dict[str, Any] | None = None,
    pit_lab_deferral: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "premise": (
            "This system is public-data-first, point-in-time, research-governed investment "
            "intelligence—not a generic AI stock picker. Optimize for economic interpretation power."
        ),
        "substrate_headline": {
            "joined_recipe_substrate_row_count": closeout_summary.get(
                "joined_recipe_substrate_row_count"
            ),
            "joined_market_metadata_flagged_count": closeout_summary.get(
                "joined_market_metadata_flagged_count"
            ),
            "no_state_change_join": closeout_summary.get("no_state_change_join"),
            "missing_excess_return_1q": closeout_summary.get("missing_excess_return_1q"),
            "thin_input_share": closeout_summary.get("thin_input_share"),
        },
        "substrate_freeze_recommendation": substrate_freeze_recommendation,
        "phase37_recommendation": phase37_recommendation,
        "residual_join_audit_tail": {
            "residual_row_count": (residual_join_summary or {}).get("residual_row_count"),
            "bucket_counts": (residual_join_summary or {}).get(
                "residual_join_bucket_counts"
            ),
        },
        "metadata_reconciliation_tail": {
            "metadata_flags_still_present_count": (
                metadata_reconciliation_summary or {}
            ).get("metadata_flags_still_present_count"),
            "metadata_flags_cleared_now_count": (
                metadata_reconciliation_summary or {}
            ).get("metadata_flags_cleared_now_count"),
        },
        "pit_lab_no_state_change_deferral": pit_lab_deferral or {},
        "next_build_agenda": {
            "hypothesis_forge": (
                "Turn stable joined recipe rows into testable hypotheses with explicit "
                "PIT windows and falsifiers."
            ),
            "pit_validation_lab": (
                "Replay joins under alternate as-of and score-run boundaries; document "
                "join_key_mismatch vs not_built separation."
            ),
            "adversarial_peer_review": (
                "Challenge factor coverage, excess definitions, and state_change lag assumptions."
            ),
            "promotion_gate": (
                "Only promote signals that survive documented data lineage and thin-input gates."
            ),
            "residual_memory_casebook": (
                "Keep registry tail, GIS misses, and immature NQ rows as explicit deferred cases—not noise."
            ),
            "user_facing_explanation_layer": (
                "Expose why-investors-should-care narratives tied to evidence bundles, not black-box scores."
            ),
        },
        "explicit_non_goals": [
            "Broad filing-index or raw-facts campaigns as headline work",
            "Threshold relaxation or production scoring logic changes without governance",
            "Large GIS concept-map expansion in the same sprint as substrate closure",
        ],
    }


def export_research_engine_handoff_brief_json(
    brief: dict[str, Any],
    out_path: str,
) -> str:
    import json
    from pathlib import Path

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())
