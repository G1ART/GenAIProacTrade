"""DB-backed export: factor_validation_summaries → promotion gate dict (Slice A pipeline)."""

from __future__ import annotations

from typing import Any

from db.records import fetch_factor_quantiles_for_run, fetch_latest_factor_validation_summaries
from metis_brain.factor_validation_gate_adapter_v0 import build_metis_gate_summary_from_factor_summary_row
from metis_brain.validation_bridge_v0 import promotion_gate_from_validation_summary


def export_promotion_gate_from_factor_validation_db(
    client: Any,
    *,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
    artifact_id: str,
) -> dict[str, Any]:
    """Return same shape as ``export-metis-gates-from-factor-validation`` CLI (ok + promotion_gate or error)."""
    factor = str(factor_name).strip()
    universe = str(universe_name).strip()
    horizon = str(horizon_type).strip()
    basis = str(return_basis or "raw").strip()
    aid = str(artifact_id).strip()
    if not aid:
        return {"ok": False, "error": "artifact_id_required"}
    rid, rows = fetch_latest_factor_validation_summaries(
        client,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
    )
    if not rid or not rows:
        return {
            "ok": False,
            "error": "no_completed_factor_validation_summary",
            "factor": factor,
            "universe": universe,
            "horizon_type": horizon,
            "hint": "Run run-factor-validation for this universe/horizon first.",
        }
    row_by = {str(r.get("return_basis")): r for r in rows}
    if basis not in row_by:
        return {
            "ok": False,
            "error": "return_basis_row_missing",
            "return_basis_requested": basis,
            "available_return_basis": sorted(row_by.keys()),
            "hint": "Pick return_basis from available keys, or re-run factor validation.",
        }
    r0 = {**dict(row_by[basis]), "run_id": rid}
    quants = fetch_factor_quantiles_for_run(
        client,
        run_id=rid,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
        return_basis=basis,
    )
    summ = build_metis_gate_summary_from_factor_summary_row(
        r0, quantiles=quants or None, return_basis=basis
    )
    gate = promotion_gate_from_validation_summary(
        artifact_id=aid,
        evaluation_run_id=rid,
        summary=summ,
    )
    try:
        gate_dict = gate.model_dump()
    except AttributeError:
        gate_dict = gate.dict()  # type: ignore[union-attr]
    return {
        "ok": True,
        "contract": "METIS_EXPORT_PROMOTION_GATE_FROM_FACTOR_VALIDATION_V0",
        "factor_validation_run_id": rid,
        "return_basis_used": basis,
        "diagnostics": {
            "sample_count": r0.get("sample_count"),
            "valid_factor_count": r0.get("valid_factor_count"),
            "spearman_rank_corr": r0.get("spearman_rank_corr"),
            "pearson_corr": r0.get("pearson_corr"),
            "factor_quantile_rows": len(quants or []),
        },
        "gate_summary_input": summ,
        "promotion_gate": gate_dict,
    }
