"""Slice B — build a Metis brain bundle with artifacts + spectrum rows **synthesized**
from live factor_validation results (no longer stub template data).

Pipeline per gate spec:
    1. Export promotion_gate from DB (existing `factor_validation_gate_export_v0`).
    2. Synthesize ``ModelArtifactPacketV0`` from the summary + quantiles (B1).
    3. Synthesize ``spectrum_rows_by_horizon[bundle_horizon]`` from the joined
       validation + factor panel rows (B2).
    4. Replace the corresponding artifact in the bundle, merge the gate (legacy
       merge), set spectrum rows, sync validation_pointer.
    5. Validate bundle integrity (same contract as ``today_spectrum.py`` reads).

The caller provides two DB-adapter callables so this module stays pure and testable.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from metis_brain.artifact_from_validation_v1 import (
    build_artifact_from_validation_v1,
    map_validation_horizon_to_bundle_horizon,
)
from metis_brain.bundle_promotion_merge_v0 import (
    merge_promotion_gate_into_bundle_dict,
    sync_artifact_validation_pointer_for_factor_run,
    validate_merged_bundle_dict,
)
from metis_brain.spectrum_rows_from_validation_v1 import (
    build_spectrum_rows_from_validation,
)

GateFetchFn = Callable[[Any, dict[str, Any]], dict[str, Any]]
JoinedFetchFn = Callable[[Any, dict[str, Any]], dict[str, Any]]


def _replace_artifact_in_bundle(
    bundle_dict: dict[str, Any], artifact_dict: dict[str, Any]
) -> dict[str, Any]:
    aid = str(artifact_dict.get("artifact_id") or "").strip()
    if not aid:
        raise ValueError("artifact_dict.artifact_id required")
    out = json.loads(json.dumps(bundle_dict, default=str))
    arts = list(out.get("artifacts") or [])
    arts = [a for a in arts if str((a or {}).get("artifact_id") or "") != aid]
    arts.append(dict(artifact_dict))
    out["artifacts"] = arts
    return out


def _set_spectrum_rows_for_horizon(
    bundle_dict: dict[str, Any],
    *,
    bundle_horizon: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = json.loads(json.dumps(bundle_dict, default=str))
    srh = dict(out.get("spectrum_rows_by_horizon") or {})
    srh[bundle_horizon] = [dict(r) for r in rows]
    out["spectrum_rows_by_horizon"] = srh
    return out


def build_bundle_full_from_validation_v1(
    *,
    template_bundle: dict[str, Any],
    gate_specs: list[dict[str, Any]],
    fetch_gate: GateFetchFn,
    fetch_joined: JoinedFetchFn,
    client: Any,
    sync_artifact_validation_pointer: bool,
    spectrum_max_rows_per_horizon: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return (bundle_dict, report). ``bundle_dict`` is None on any failure.

    ``fetch_joined(client, spec)`` must return a dict with keys:
        - ``ok`` (bool)
        - ``summary_row`` (dict)     — a single row from factor_validation_summaries
        - ``quantile_rows`` (list)   — factor_quantile_results for run/factor/basis
        - ``joined_rows`` (list)     — validation_panel × factor_panel joined rows
                                       (each has ``symbol``, factor_name column,
                                       ``fiscal_year``, ``fiscal_period``, ``accession_no``)
        - ``run_id`` (str)
    """
    merged: dict[str, Any] = json.loads(json.dumps(template_bundle, default=str))
    steps: list[dict[str, Any]] = []

    for spec in gate_specs:
        spec = {k: str(v).strip() for k, v in spec.items() if k in {
            "factor_name", "universe_name", "horizon_type", "return_basis", "artifact_id",
        }}
        ex = fetch_gate(client, spec)
        step: dict[str, Any] = {"spec": spec, "gate_export_ok": bool(ex.get("ok"))}
        steps.append(step)
        if not ex.get("ok"):
            return None, {
                "integrity_ok": False,
                "errors": [f"gate_export_failed:{ex.get('error')}"],
                "steps": steps,
                "aborted_reason": "gate_export_failed",
            }
        gate = ex.get("promotion_gate")
        if not isinstance(gate, dict):
            return None, {
                "integrity_ok": False,
                "errors": ["promotion_gate_missing_in_export"],
                "steps": steps,
                "aborted_reason": "invalid_gate_export",
            }

        jx = fetch_joined(client, spec)
        step["joined_fetch_ok"] = bool(jx.get("ok"))
        if not jx.get("ok"):
            return None, {
                "integrity_ok": False,
                "errors": [f"joined_fetch_failed:{jx.get('error')}"],
                "steps": steps,
                "aborted_reason": "joined_fetch_failed",
            }
        summary_row = jx.get("summary_row") or {}
        quantile_rows = jx.get("quantile_rows") or []
        joined_rows = jx.get("joined_rows") or []
        run_id = str(jx.get("run_id") or "").strip()
        if not run_id:
            return None, {
                "integrity_ok": False,
                "errors": ["joined_fetch_missing_run_id"],
                "steps": steps,
                "aborted_reason": "joined_fetch_failed",
            }

        artifact = build_artifact_from_validation_v1(
            factor_name=spec["factor_name"],
            universe_name=spec["universe_name"],
            horizon_type=spec["horizon_type"],
            return_basis=spec.get("return_basis") or "raw",
            artifact_id=spec["artifact_id"],
            run_id=run_id,
            summary_row=summary_row,
            quantile_rows=quantile_rows,
        )
        bundle_horizon, spectrum_rows = build_spectrum_rows_from_validation(
            factor_name=spec["factor_name"],
            horizon_type=spec["horizon_type"],
            summary_row=summary_row,
            joined_rows=joined_rows,
            max_rows=spectrum_max_rows_per_horizon,
        )
        step["bundle_horizon"] = bundle_horizon
        step["spectrum_row_count"] = len(spectrum_rows)
        step["artifact_id"] = artifact.get("artifact_id")

        if not spectrum_rows:
            return None, {
                "integrity_ok": False,
                "errors": [
                    f"no_spectrum_rows_synthesized:factor={spec['factor_name']}"
                    f";horizon={bundle_horizon};universe={spec['universe_name']}"
                ],
                "steps": steps,
                "aborted_reason": "no_spectrum_rows",
            }

        try:
            merged = _replace_artifact_in_bundle(merged, artifact)
            merged = merge_promotion_gate_into_bundle_dict(merged, gate)
            merged = _set_spectrum_rows_for_horizon(
                merged,
                bundle_horizon=bundle_horizon,
                rows=spectrum_rows,
            )
            if sync_artifact_validation_pointer:
                merged = sync_artifact_validation_pointer_for_factor_run(
                    merged,
                    artifact_id=str(gate.get("artifact_id") or ""),
                    evaluation_run_id=str(gate.get("evaluation_run_id") or ""),
                )
        except ValueError as e:
            return None, {
                "integrity_ok": False,
                "errors": [f"merge_failed:{e}"],
                "steps": steps,
                "aborted_reason": "merge_failed",
            }

    integrity_ok, errs = validate_merged_bundle_dict(merged)
    report: dict[str, Any] = {
        "integrity_ok": integrity_ok,
        "errors": errs,
        "steps": steps,
    }
    if not integrity_ok:
        report["aborted_reason"] = "integrity_failed"
        return None, report
    report["aborted_reason"] = None
    return merged, report


def fetch_joined_rows_for_factor_db(
    client: Any, spec: dict[str, Any]
) -> dict[str, Any]:
    """DB adapter: fetches summary_row + quantile_rows + joined_rows for one gate spec.

    Reuses the primitives in ``research.validation_runner``:
      * ``resolve_slice_symbols(client, universe_name)``
      * ``fetch_factor_market_validation_panels_for_symbols(...)``
      * ``fetch_issuer_quarter_factor_panels_for_accessions(...)``
    """
    from db.records import (
        fetch_factor_market_validation_panels_for_symbols,
        fetch_factor_quantiles_for_run,
        fetch_issuer_quarter_factor_panels_for_accessions,
        fetch_latest_factor_validation_summaries,
        issuer_quarter_factor_panel_join_key,
    )
    from research.universe_slices import resolve_slice_symbols

    factor = str(spec.get("factor_name") or "").strip()
    universe = str(spec.get("universe_name") or "").strip()
    horizon = str(spec.get("horizon_type") or "").strip()
    basis = str(spec.get("return_basis") or "raw").strip()

    run_id, rows = fetch_latest_factor_validation_summaries(
        client,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
    )
    if not run_id or not rows:
        return {"ok": False, "error": "no_completed_validation_summary"}
    summary = next((r for r in rows if str(r.get("return_basis")) == basis), None)
    if summary is None:
        return {
            "ok": False,
            "error": "return_basis_row_missing",
            "available_return_basis": sorted({str(r.get("return_basis")) for r in rows}),
        }

    quantile_rows = fetch_factor_quantiles_for_run(
        client,
        run_id=run_id,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
        return_basis=basis,
    ) or []

    symbols = resolve_slice_symbols(client, universe)
    vpanels = fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=8000
    )
    accessions = sorted({str(p.get("accession_no")) for p in vpanels if p.get("accession_no")})
    fp_map = fetch_issuer_quarter_factor_panels_for_accessions(
        client, accession_nos=accessions, limit_per_batch=8000
    )

    joined: list[dict[str, Any]] = []
    for vp in vpanels:
        key = issuer_quarter_factor_panel_join_key(
            vp.get("cik"),
            vp.get("accession_no"),
            vp.get("factor_version"),
            default_factor_version="v1",
        )
        fp = fp_map.get(key)
        if fp is None:
            continue
        factor_value = fp.get(factor)
        if factor_value is None:
            continue
        joined.append({
            "symbol": vp.get("symbol"),
            "cik": vp.get("cik"),
            "accession_no": vp.get("accession_no"),
            "fiscal_year": fp.get("fiscal_year"),
            "fiscal_period": fp.get("fiscal_period"),
            factor: factor_value,
        })

    return {
        "ok": True,
        "run_id": run_id,
        "summary_row": dict(summary),
        "quantile_rows": [dict(q) for q in quantile_rows],
        "joined_rows": joined,
    }
