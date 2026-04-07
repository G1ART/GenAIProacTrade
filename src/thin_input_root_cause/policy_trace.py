"""Trace which policy branch forces thin_input (Phase 26, mirrors public_core.quality)."""

from __future__ import annotations

from typing import Any

from public_core.quality import (
    DEGRADED_HARNESS_ERROR_FRAC,
    STRONG_ALT_INSUFFICIENT_FRAC,
    STRONG_ALT_MIN_WATCHLIST,
    STRONG_INSUFFICIENT_FRAC,
    STRONG_MIN_CASEBOOK,
    STRONG_MIN_WATCHLIST,
    THIN_INPUT_COMBO_GATING_FRAC,
    THIN_INPUT_COMBO_INSUFFICIENT_FRAC,
    THIN_INPUT_INSUFFICIENT_FRAC,
    classify_cycle_quality,
    rank_gap_reasons,
)


def trace_thin_input_rule(
    *,
    cycle_ok: bool,
    scanner_failed: bool,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    thin_input 로 분류될 때 어떤 임계/조합이 걸렸는지(복기 전용).
    """
    q = classify_cycle_quality(
        cycle_ok=cycle_ok, scanner_failed=scanner_failed, metrics=metrics
    )
    stmap = metrics.get("stage_status_by_name") or {}
    branches: list[str] = []
    if not cycle_ok or scanner_failed:
        branches.append("branch_not_ok_or_scanner_failed")
    for key in ("harness_inputs", "investigation_memos", "outlier_casebook"):
        if stmap.get(key) == "failed":
            branches.append(f"branch_stage_failed:{key}")
    if float(metrics.get("harness_error_rate") or 0) > DEGRADED_HARNESS_ERROR_FRAC:
        branches.append("branch_harness_error_rate_degraded")

    p_ins = float(metrics.get("insufficient_data_fraction") or 0)
    p_gate = float(metrics.get("gating_high_missingness_fraction") or 0)
    wl = int(metrics.get("watchlist_selected") or 0)
    ce = int(metrics.get("casebook_entries_created") or 0)

    thin_reasons: list[str] = []
    if p_ins >= THIN_INPUT_INSUFFICIENT_FRAC:
        thin_reasons.append(
            f"insufficient_data_fraction>={THIN_INPUT_INSUFFICIENT_FRAC} (actual {p_ins:.4f})"
        )
    if p_ins >= THIN_INPUT_COMBO_INSUFFICIENT_FRAC and p_gate >= THIN_INPUT_COMBO_GATING_FRAC:
        thin_reasons.append(
            f"combo insufficient>={THIN_INPUT_COMBO_INSUFFICIENT_FRAC} "
            f"and gating>={THIN_INPUT_COMBO_GATING_FRAC} "
            f"(actual ins={p_ins:.4f} gate={p_gate:.4f})"
        )

    near_strong = (
        p_ins < STRONG_INSUFFICIENT_FRAC
        and wl >= STRONG_MIN_WATCHLIST
        and ce >= STRONG_MIN_CASEBOOK
    ) or (
        p_ins < STRONG_ALT_INSUFFICIENT_FRAC and wl >= STRONG_ALT_MIN_WATCHLIST
    )

    return {
        "quality_class": q,
        "threshold_constants": {
            "THIN_INPUT_INSUFFICIENT_FRAC": THIN_INPUT_INSUFFICIENT_FRAC,
            "THIN_INPUT_COMBO_INSUFFICIENT_FRAC": THIN_INPUT_COMBO_INSUFFICIENT_FRAC,
            "THIN_INPUT_COMBO_GATING_FRAC": THIN_INPUT_COMBO_GATING_FRAC,
            "STRONG_INSUFFICIENT_FRAC": STRONG_INSUFFICIENT_FRAC,
            "STRONG_MIN_WATCHLIST": STRONG_MIN_WATCHLIST,
            "STRONG_MIN_CASEBOOK": STRONG_MIN_CASEBOOK,
            "STRONG_ALT_INSUFFICIENT_FRAC": STRONG_ALT_INSUFFICIENT_FRAC,
            "STRONG_ALT_MIN_WATCHLIST": STRONG_ALT_MIN_WATCHLIST,
            "DEGRADED_HARNESS_ERROR_FRAC": DEGRADED_HARNESS_ERROR_FRAC,
        },
        "metric_snapshot": {
            "insufficient_data_fraction": p_ins,
            "gating_high_missingness_fraction": p_gate,
            "watchlist_selected": wl,
            "casebook_entries_created": ce,
            "candidates_scanned": metrics.get("candidates_scanned"),
        },
        "failure_branches_evaluated": branches,
        "thin_classification_reasons": thin_reasons,
        "near_strong_gate": near_strong,
        "gap_reasons_ranked": rank_gap_reasons(metrics),
    }


def classify_with_hypothetical_thresholds(
    *,
    cycle_ok: bool,
    scanner_failed: bool,
    metrics: dict[str, Any],
    thin_insufficient_frac: float,
    thin_combo_insufficient_frac: float,
    thin_combo_gating_frac: float,
) -> str:
    """진단 전용: 상수를 바꿔 가상 분류(런타임 정책은 변경하지 않음)."""
    if not cycle_ok or scanner_failed:
        return "failed"
    stmap = metrics.get("stage_status_by_name") or {}
    for key in ("harness_inputs", "investigation_memos", "outlier_casebook"):
        if stmap.get(key) == "failed":
            return "degraded"
    if float(metrics.get("harness_error_rate") or 0) > DEGRADED_HARNESS_ERROR_FRAC:
        return "degraded"

    p_ins = float(metrics.get("insufficient_data_fraction") or 0)
    p_gate = float(metrics.get("gating_high_missingness_fraction") or 0)
    wl = int(metrics.get("watchlist_selected") or 0)
    ce = int(metrics.get("casebook_entries_created") or 0)

    if p_ins >= thin_insufficient_frac or (
        p_ins >= thin_combo_insufficient_frac and p_gate >= thin_combo_gating_frac
    ):
        return "thin_input"

    if (
        p_ins < STRONG_INSUFFICIENT_FRAC
        and wl >= STRONG_MIN_WATCHLIST
        and ce >= STRONG_MIN_CASEBOOK
    ):
        return "strong"
    if p_ins < STRONG_ALT_INSUFFICIENT_FRAC and wl >= STRONG_ALT_MIN_WATCHLIST:
        return "strong"
    return "usable_with_gaps"


def report_quality_threshold_sensitivity(
    *,
    cycle_ok: bool,
    scanner_failed: bool,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """현재 임계 vs 소폭 이동 시 가상 quality_class 분포."""
    base = classify_cycle_quality(
        cycle_ok=cycle_ok, scanner_failed=scanner_failed, metrics=metrics
    )
    p_ins = float(metrics.get("insufficient_data_fraction") or 0)
    scenarios: list[dict[str, Any]] = []

    for label, t_ins, t_ci, t_cg in (
        ("relax_thin_insufficient_to_085", 0.85, THIN_INPUT_COMBO_INSUFFICIENT_FRAC, THIN_INPUT_COMBO_GATING_FRAC),
        ("relax_thin_insufficient_to_090", 0.90, THIN_INPUT_COMBO_INSUFFICIENT_FRAC, THIN_INPUT_COMBO_GATING_FRAC),
        ("tighten_combo_gating_to_030", THIN_INPUT_INSUFFICIENT_FRAC, THIN_INPUT_COMBO_INSUFFICIENT_FRAC, 0.30),
        ("tighten_combo_insufficient_to_055", THIN_INPUT_INSUFFICIENT_FRAC, 0.55, THIN_INPUT_COMBO_GATING_FRAC),
    ):
        qc = classify_with_hypothetical_thresholds(
            cycle_ok=cycle_ok,
            scanner_failed=scanner_failed,
            metrics=metrics,
            thin_insufficient_frac=t_ins,
            thin_combo_insufficient_frac=t_ci,
            thin_combo_gating_frac=t_cg,
        )
        scenarios.append({"label": label, "hypothetical_quality_class": qc})

    all_thin = all(s["hypothetical_quality_class"] == "thin_input" for s in scenarios)
    collapse_note = (
        "모든 나열 시나리오에서 여전히 thin_input → 정책 민감도가 낮고 후보 데이터 자체가 얇을 가능성."
        if all_thin and base == "thin_input"
        else None
    )

    return {
        "ok": True,
        "review_only": True,
        "no_automatic_threshold_mutation": True,
        "current_quality_class": base,
        "current_insufficient_data_fraction": p_ins,
        "scenarios": scenarios,
        "all_listed_scenarios_remain_thin_input": all_thin,
        "note": collapse_note,
    }


def report_quality_threshold_sensitivity_for_universe(
    client: Any,
    *,
    universe_name: str,
    quality_run_lookback: int = 40,
) -> dict[str, Any]:
    """최근 thin_input 사이클 품질 행의 metrics_json 기준 민감도(첫 매칭)."""
    from db import records as dbrec

    rows = dbrec.fetch_public_core_cycle_quality_runs_for_universe(
        client, universe_name=universe_name, limit=quality_run_lookback
    )
    for r in rows:
        if str(r.get("quality_class") or "") != "thin_input":
            continue
        mj = r.get("metrics_json") if isinstance(r.get("metrics_json"), dict) else {}
        out = report_quality_threshold_sensitivity(
            cycle_ok=bool(r.get("cycle_finished_ok", True)),
            scanner_failed=bool(r.get("scanner_failed", False)),
            metrics=mj,
        )
        out["source_quality_run_id"] = r.get("id")
        return out
    return {
        "ok": False,
        "error": "no_thin_input_quality_run_in_lookback",
        "review_only": True,
        "no_automatic_threshold_mutation": True,
    }
