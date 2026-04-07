"""Thin-input drivers: cycle quality (Phase 13) + joined-substrate row flags (Phase 26)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from db import records as dbrec
from public_buildout.revalidation import build_revalidation_trigger
from public_depth.diagnostics import compute_substrate_coverage
from public_repair_iteration.resolver import resolve_program_id
from public_core.quality import (
    THIN_INPUT_COMBO_GATING_FRAC,
    THIN_INPUT_COMBO_INSUFFICIENT_FRAC,
    THIN_INPUT_INSUFFICIENT_FRAC,
)
from thin_input_root_cause.policy_trace import trace_thin_input_rule


def _joined_row_driver_bucket(row: dict[str, Any]) -> str:
    pj = row.get("panel_json") if isinstance(row.get("panel_json"), dict) else {}
    flags = pj.get("quality_flags") or []
    if not isinstance(flags, list):
        flags = []
    fs = {str(f) for f in flags}
    if not fs:
        return "joined_panel_json_clean_no_quality_flags"
    if "missing_market_metadata" in fs:
        return "joined_but_market_metadata_flagged"
    if "missing_forward_return_1q" in fs or "missing_forward_return_1m" in fs:
        return "joined_but_forward_quality_flags_present"
    if "missing_state_change_score" in fs:
        return "joined_but_stale_sc_flag_in_panel_json"
    return "joined_with_other_quality_flags"


def report_thin_input_drivers(
    client: Any,
    *,
    universe_name: str,
    program_id_raw: str | None = None,
    panel_limit: int = 8000,
    quality_run_lookback: int = 40,
    joined_sample_limit: int = 25,
) -> dict[str, Any]:
    joined: list[dict[str, Any]] = []
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        quality_run_lookback=quality_run_lookback,
        joined_panels_out=joined,
    )

    raw_pi = str(program_id_raw or "latest").strip()
    prog_resolve = resolve_program_id(
        client, raw_pi, universe_name=universe_name.strip()
    )
    pid = str(prog_resolve["program_id"]) if prog_resolve.get("ok") else None

    rerun = (
        build_revalidation_trigger(client, program_id=pid)
        if pid
        else {"ok": False, "skipped": True, "reason": "program_id_unresolved"}
    )

    qruns = dbrec.fetch_public_core_cycle_quality_runs_for_universe(
        client, universe_name=universe_name, limit=quality_run_lookback
    )

    cycle_driver_counts: Counter[str] = Counter()
    cycle_traces: list[dict[str, Any]] = []
    thin_run_rows: list[dict[str, Any]] = []

    for r in qruns:
        qc = str(r.get("quality_class") or "")
        mj = r.get("metrics_json") if isinstance(r.get("metrics_json"), dict) else {}
        cyc_ok = bool(r.get("cycle_finished_ok", True))
        scan_fail = bool(r.get("scanner_failed", False))
        if qc == "thin_input":
            thin_run_rows.append(
                {
                    "id": r.get("id"),
                    "created_at": r.get("created_at"),
                    "quality_class": qc,
                }
            )
            tr = trace_thin_input_rule(
                cycle_ok=cyc_ok, scanner_failed=scan_fail, metrics=mj
            )
            p_ins = float(mj.get("insufficient_data_fraction") or 0)
            p_gate = float(mj.get("gating_high_missingness_fraction") or 0)
            if p_ins >= THIN_INPUT_INSUFFICIENT_FRAC:
                driver = "thin_insufficient_ge_075"
            elif (
                p_ins >= THIN_INPUT_COMBO_INSUFFICIENT_FRAC
                and p_gate >= THIN_INPUT_COMBO_GATING_FRAC
            ):
                driver = "thin_combo_insufficient_and_gating"
            else:
                driver = "thin_input_metrics_below_thin_thresholds_unexpected"
            cycle_driver_counts[driver] += 1
            if len(cycle_traces) < 5:
                cycle_traces.append(
                    {
                        "quality_run_id": r.get("id"),
                        "trace": tr,
                    }
                )

    joined_bucket_counts: Counter[str] = Counter()
    for row in joined:
        joined_bucket_counts[_joined_row_driver_bucket(row)] += 1

    joined_samples: list[dict[str, Any]] = []
    for row in joined[:joined_sample_limit]:
        joined_samples.append(
            {
                "symbol": row.get("symbol"),
                "cik": row.get("cik"),
                "accession_no": row.get("accession_no"),
                "signal_available_date": row.get("signal_available_date"),
                "joined_row_driver": _joined_row_driver_bucket(row),
                "panel_quality_flags": (row.get("panel_json") or {}).get("quality_flags"),
            }
        )

    dominant_joined_blockers = [
        {"reason": k, "count": v}
        for k, v in joined_bucket_counts.most_common()
        if k != "joined_panel_json_clean_no_quality_flags"
    ]

    return {
        "ok": True,
        "universe_name": universe_name,
        "program_id": pid,
        "program_resolve": {
            "ok": bool(prog_resolve.get("ok")),
            "error": prog_resolve.get("error"),
        },
        "substrate_metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "rerun_readiness": rerun,
        "cycle_quality_note": (
            "thin_input_share 은 public_core_cycle_quality_runs 의 quality_class 비율에서 온다. "
            "joined recipe 행 품질과는 별개 축이다."
        ),
        "thin_input_quality_runs_in_lookback": len(thin_run_rows),
        "cycle_thin_driver_counts": dict(cycle_driver_counts),
        "cycle_trace_samples": cycle_traces,
        "joined_substrate_row_count": len(joined),
        "joined_substrate_driver_counts": dict(joined_bucket_counts),
        "joined_substrate_dominant_blockers": dominant_joined_blockers[:12],
        "joined_substrate_representative_samples": joined_samples,
        "dominant_exclusion_reasons": metrics.get("dominant_exclusion_reasons"),
    }


def rank_leverageable_blocker(decomposition: dict[str, Any]) -> str:
    ex = decomposition.get("exclusion_distribution") or {}
    order = sorted(
        [(k, int(v)) for k, v in ex.items() if int(v) > 0],
        key=lambda x: -x[1],
    )
    if not order:
        return "none"
    return str(order[0][0])
