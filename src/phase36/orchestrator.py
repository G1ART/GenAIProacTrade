"""Phase 36 오케스트레이션: 메타 정합·잔여 SC·freeze·handoff brief."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase33.gis_narrow import inspect_gis_raw_present_no_silver_deterministic
from phase33.metrics import collect_phase33_substrate_snapshot
from phase35.orchestrator import PHASE34_IMMATURE_SYMBOLS

from phase36.joined_metadata_reconciliation import (
    report_joined_metadata_flag_reconciliation_targets,
    run_joined_metadata_reconciliation_repair,
    run_joined_metadata_reconciliation_repair_two_pass,
)
from phase36.phase35_bundle_io import load_phase35_bundle
from phase36.residual_pit_deferral import build_residual_pit_deferral_summary
from phase36.phase37_recommend import recommend_phase37_after_phase36
from phase36.research_handoff_brief import build_research_engine_handoff_brief
from phase36.residual_state_change_join import (
    report_residual_state_change_join_gaps,
    run_residual_state_change_join_repair,
)
from phase36.substrate_freeze_readiness import report_substrate_freeze_readiness


def run_phase36_substrate_freeze_and_research_handoff(
    settings: Any,
    *,
    universe_name: str,
    phase35_bundle_path: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    state_change_scores_limit: int = 50_000,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    _ = load_phase35_bundle(phase35_bundle_path)

    before = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    meta_targets = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
    )

    meta_repair = run_joined_metadata_reconciliation_repair(
        settings,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
    )

    residual_repair = run_residual_state_change_join_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
    )

    after = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    gis_out = inspect_gis_raw_present_no_silver_deterministic(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    residual_after = residual_repair.get("report_after") or {}
    pit_deferral = build_residual_pit_deferral_summary(residual_after)
    meta_summary = {
        "metadata_flags_cleared_now_count": int(
            meta_repair.get("metadata_flags_cleared_now_count") or 0
        ),
        "metadata_flags_still_present_count": int(
            meta_repair.get("metadata_flags_still_present_count") or 0
        ),
    }

    freeze = report_substrate_freeze_readiness(
        snapshot_after=after,
        metadata_reconciliation=meta_summary,
        residual_join_report_after=residual_after,
        gis_outcome=str(gis_out.get("outcome") or ""),
        immature_forward_symbol_count=len(PHASE34_IMMATURE_SYMBOLS),
    )

    p37 = recommend_phase37_after_phase36(freeze_report=freeze)

    closeout_summary = {
        "joined_recipe_substrate_row_count": int(
            after.get("joined_recipe_substrate_row_count") or 0
        ),
        "joined_market_metadata_flagged_count": int(
            after.get("joined_market_metadata_flagged_count") or 0
        ),
        "thin_input_share": after.get("thin_input_share"),
        "missing_excess_return_1q": int(after.get("missing_excess_return_1q") or 0),
        "missing_validation_symbol_count": int(
            after.get("missing_validation_symbol_count") or 0
        ),
        "missing_quarter_snapshot_for_cik": int(
            after.get("missing_quarter_snapshot_for_cik") or 0
        ),
        "factor_panel_missing_for_resolved_cik": int(
            after.get("factor_panel_missing_for_resolved_cik") or 0
        ),
        "no_state_change_join": int(
            (after.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
        ),
        "metadata_flags_cleared_now_count": meta_summary["metadata_flags_cleared_now_count"],
        "metadata_flags_still_present_count": meta_summary[
            "metadata_flags_still_present_count"
        ],
        "no_state_change_join_cleared_now_count": int(
            residual_repair.get("no_state_change_join_cleared_now_count") or 0
        ),
        "residual_join_rows_still_blocked_count": int(
            residual_repair.get("residual_join_rows_still_blocked_count") or 0
        ),
        "maturity_deferred_symbol_count": len(PHASE34_IMMATURE_SYMBOLS),
        "gis_outcome": gis_out.get("outcome"),
        "substrate_freeze_recommendation": freeze.get("substrate_freeze_recommendation"),
        "phase37_recommendation": p37.get("phase37_recommendation"),
    }

    brief = build_research_engine_handoff_brief(
        universe_name=universe_name,
        closeout_summary=closeout_summary,
        substrate_freeze_recommendation=str(
            freeze.get("substrate_freeze_recommendation") or ""
        ),
        phase37_recommendation=str(p37.get("phase37_recommendation") or ""),
        residual_join_summary={
            "residual_row_count": residual_after.get("residual_row_count"),
            "residual_join_bucket_counts": residual_after.get(
                "residual_join_bucket_counts"
            ),
        },
        metadata_reconciliation_summary=meta_summary,
        pit_lab_deferral=pit_deferral,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase35_bundle_path": phase35_bundle_path,
        "phase37_recommendation": p37.get("phase37_recommendation"),
        "before": before,
        "after": after,
        "joined_metadata_flag_reconciliation_targets": meta_targets,
        "joined_metadata_reconciliation_repair": meta_repair,
        "residual_pit_deferral": pit_deferral,
        "residual_state_change_join_repair": residual_repair,
        "gis_deterministic_inspect": gis_out,
        "substrate_freeze_readiness": freeze,
        "research_engine_handoff_brief": brief,
        "phase37": p37,
        "closeout_summary": closeout_summary,
    }


def run_phase36_1_complete_narrow_integrity_round(
    settings: Any,
    *,
    universe_name: str,
    phase35_bundle_path: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    state_change_scores_limit: int = 50_000,
) -> dict[str, Any]:
    """
    Phase 36.1: 2패스 메타 정합 → 잔여 SC는 감사만(PIT defer) → freeze 재평가 → handoff.
    광역 state_change·filing·GIS 확대 없음.
    """
    client = get_supabase_client(settings)
    _ = load_phase35_bundle(phase35_bundle_path)

    before = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    meta_targets = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
    )

    meta_repair = run_joined_metadata_reconciliation_repair_two_pass(
        settings,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
    )

    residual_report = report_residual_state_change_join_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
    )
    pit_deferral = build_residual_pit_deferral_summary(residual_report)

    after = collect_phase33_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    gis_out = inspect_gis_raw_present_no_silver_deterministic(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    meta_summary = {
        "metadata_flags_cleared_now_count": int(
            meta_repair.get("metadata_flags_cleared_now_count") or 0
        ),
        "metadata_flags_still_present_count": int(
            meta_repair.get("metadata_flags_still_present_count") or 0
        ),
    }

    freeze = report_substrate_freeze_readiness(
        snapshot_after=after,
        metadata_reconciliation=meta_summary,
        residual_join_report_after=residual_report,
        gis_outcome=str(gis_out.get("outcome") or ""),
        immature_forward_symbol_count=len(PHASE34_IMMATURE_SYMBOLS),
    )

    p37 = recommend_phase37_after_phase36(freeze_report=freeze)

    rb = meta_repair.get("report_before") or {}
    rm = meta_repair.get("report_mid") or {}
    ra = meta_repair.get("report_after") or {}

    closeout_summary = {
        "joined_recipe_substrate_row_count": int(
            after.get("joined_recipe_substrate_row_count") or 0
        ),
        "joined_market_metadata_flagged_count": int(
            after.get("joined_market_metadata_flagged_count") or 0
        ),
        "thin_input_share": after.get("thin_input_share"),
        "missing_excess_return_1q": int(after.get("missing_excess_return_1q") or 0),
        "missing_validation_symbol_count": int(
            after.get("missing_validation_symbol_count") or 0
        ),
        "missing_quarter_snapshot_for_cik": int(
            after.get("missing_quarter_snapshot_for_cik") or 0
        ),
        "factor_panel_missing_for_resolved_cik": int(
            after.get("factor_panel_missing_for_resolved_cik") or 0
        ),
        "no_state_change_join": int(
            (after.get("exclusion_distribution") or {}).get("no_state_change_join") or 0
        ),
        "metadata_flags_cleared_now_count": meta_summary["metadata_flags_cleared_now_count"],
        "metadata_flags_still_present_count": meta_summary[
            "metadata_flags_still_present_count"
        ],
        "metadata_reconciliation_bucket_counts_before": dict(
            rb.get("reconciliation_bucket_counts") or {}
        ),
        "metadata_reconciliation_bucket_counts_mid": dict(
            rm.get("reconciliation_bucket_counts") or {}
        ),
        "metadata_reconciliation_bucket_counts_after": dict(
            ra.get("reconciliation_bucket_counts") or {}
        ),
        "validation_rebuild_target_count_after_hydration": int(
            meta_repair.get("validation_rebuild_target_count_after_hydration") or 0
        ),
        "residual_join_rows_still_blocked_count": int(
            residual_report.get("residual_row_count") or 0
        ),
        "residual_pit_deferred_row_count": pit_deferral.get("deferred_row_count"),
        "maturity_deferred_symbol_count": len(PHASE34_IMMATURE_SYMBOLS),
        "gis_outcome": gis_out.get("outcome"),
        "substrate_freeze_recommendation": freeze.get("substrate_freeze_recommendation"),
        "phase37_recommendation": p37.get("phase37_recommendation"),
    }

    brief = build_research_engine_handoff_brief(
        universe_name=universe_name,
        closeout_summary=closeout_summary,
        substrate_freeze_recommendation=str(
            freeze.get("substrate_freeze_recommendation") or ""
        ),
        phase37_recommendation=str(p37.get("phase37_recommendation") or ""),
        residual_join_summary={
            "residual_row_count": residual_report.get("residual_row_count"),
            "residual_join_bucket_counts": residual_report.get(
                "residual_join_bucket_counts"
            ),
        },
        metadata_reconciliation_summary=meta_summary,
        pit_lab_deferral=pit_deferral,
    )

    return {
        "ok": True,
        "phase": "phase36_1_complete_narrow_integrity_round",
        "universe_name": universe_name,
        "phase35_bundle_path": phase35_bundle_path,
        "phase37_recommendation": p37.get("phase37_recommendation"),
        "before": before,
        "after": after,
        "joined_metadata_flag_reconciliation_targets": meta_targets,
        "joined_metadata_reconciliation_two_pass": meta_repair,
        "residual_state_change_join_report": residual_report,
        "residual_pit_deferral": pit_deferral,
        "gis_deterministic_inspect": gis_out,
        "substrate_freeze_readiness": freeze,
        "research_engine_handoff_brief": brief,
        "phase37": p37,
        "closeout_summary": closeout_summary,
    }
