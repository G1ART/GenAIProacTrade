"""Phase 36-C: 공개 코어 기판 freeze / 연구 엔진 전환 판정(비모호)."""

from __future__ import annotations

from typing import Any

FREEZE_PUBLIC_CORE = "freeze_public_core_and_shift_to_research_engine"
ONE_MORE_NARROW = "one_more_narrow_integrity_round_then_freeze"
STILL_BLOCKED = "still_blocked_by_high_impact_structural_gap"


def report_substrate_freeze_readiness(
    *,
    snapshot_after: dict[str, Any],
    metadata_reconciliation: dict[str, Any] | None = None,
    residual_join_report_after: dict[str, Any] | None = None,
    gis_outcome: str | None = None,
    immature_forward_symbol_count: int = 7,
) -> dict[str, Any]:
    """
    남은 이슈를 tail / calendar / mapping / structural 로 요약하고
    substrate_freeze_recommendation 을 셋 중 하나로 고정한다.
    """
    joined = int(snapshot_after.get("joined_recipe_substrate_row_count") or 0)
    thin = snapshot_after.get("thin_input_share")
    thin_f = float(thin) if thin is not None else None

    meta_still = int(
        (metadata_reconciliation or {}).get("metadata_flags_still_present_count") or 0
    )

    residual_rows = list(
        (residual_join_report_after or {}).get("rows") or []
    )
    residual_n = len(residual_rows)
    repairable_residual = sum(
        1
        for r in residual_rows
        if str(r.get("residual_join_bucket") or "")
        == "state_change_not_built_for_row"
    )

    blocker_mix = {
        "low_roi_registry_tail": int(
            snapshot_after.get("missing_validation_symbol_count") or 0
        ),
        "factor_or_quarter_snapshot_tail": max(
            int(snapshot_after.get("factor_panel_missing_for_resolved_cik") or 0),
            int(snapshot_after.get("missing_quarter_snapshot_for_cik") or 0),
        ),
        "external_calendar_maturity_blockers": int(immature_forward_symbol_count),
        "narrow_gis_mapping_blocker": 1
        if gis_outcome
        in (
            "blocked_unmapped_concepts_remain_in_sample",
            "blocked",
        )
        else 0,
        "joined_substrate_headline_rows": joined,
    }

    rationale_parts: list[str] = []

    if thin_f is not None and thin_f >= 0.99 and joined < 50:
        rationale_parts.append(
            "thin_input_share_near_full_with_very_low_joined_count_treat_as_structural_break"
        )
        return {
            "ok": True,
            "blocker_mix": blocker_mix,
            "substrate_freeze_recommendation": STILL_BLOCKED,
            "rationale": "; ".join(rationale_parts),
        }

    if joined < 1:
        rationale_parts.append("empty_joined_substrate")
        return {
            "ok": True,
            "blocker_mix": blocker_mix,
            "substrate_freeze_recommendation": STILL_BLOCKED,
            "rationale": "; ".join(rationale_parts),
        }

    rationale_parts.append(
        "headline_joined_stable_registry_tail_treated_as_low_roi_deferred"
    )

    if meta_still > 0 or repairable_residual > 0:
        rationale_parts.append(
            f"metadata_flags_still_{meta_still}_or_repairable_residual_sc_{repairable_residual}"
        )
        return {
            "ok": True,
            "blocker_mix": blocker_mix,
            "substrate_freeze_recommendation": ONE_MORE_NARROW,
            "rationale": "; ".join(rationale_parts),
        }

    if residual_n > 0:
        rationale_parts.append(
            f"residual_no_sc_rows_{residual_n}_non_repairable_buckets_only_defer_pit_lab"
        )

    rationale_parts.append(
        "shift_primary_build_energy_to_research_engine_and_user_facing_layer"
    )
    return {
        "ok": True,
        "blocker_mix": blocker_mix,
        "substrate_freeze_recommendation": FREEZE_PUBLIC_CORE,
        "rationale": "; ".join(rationale_parts),
    }
