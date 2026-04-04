"""Deterministic AI Harness v1 input materialization from Phase 4–6 tables."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from db import records as dbrec
from harness.contracts import HARNESS_INPUT_CONTRACT_VERSION


def _json_hash(obj: dict[str, Any]) -> str:
    s = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _fetch_run(client: Any, run_id: str) -> Optional[dict[str, Any]]:
    r = client.table("state_change_runs").select("*").eq("id", run_id).limit(1).execute()
    if not r.data:
        return None
    return dict(r.data[0])


def _fetch_score(
    client: Any, *, run_id: str, cik: str, as_of: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_state_change_scores")
        .select("*")
        .eq("run_id", run_id)
        .eq("cik", cik)
        .eq("as_of_date", as_of)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def _fetch_components(
    client: Any, *, run_id: str, cik: str, as_of: str
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_state_change_components")
        .select("*")
        .eq("run_id", run_id)
        .eq("cik", cik)
        .eq("as_of_date", as_of)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def _fetch_issuer(client: Any, issuer_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not issuer_id:
        return None
    r = client.table("issuer_master").select("*").eq("id", issuer_id).limit(1).execute()
    if not r.data:
        return None
    return dict(r.data[0])


def _fetch_latest_factor_panel(client: Any, cik: str) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .eq("cik", cik)
        .limit(80)
        .execute()
    )
    rows = [dict(x) for x in (r.data or [])]
    if not rows:
        return None
    rows.sort(
        key=lambda x: (int(x.get("fiscal_year") or 0), str(x.get("fiscal_period") or "")),
        reverse=True,
    )
    return rows[0]


def _fetch_validation_panel(
    client: Any, *, cik: str, accession_no: Optional[str]
) -> Optional[dict[str, Any]]:
    if accession_no:
        r = (
            client.table("factor_market_validation_panels")
            .select("*")
            .eq("cik", cik)
            .eq("accession_no", accession_no)
            .limit(1)
            .execute()
        )
        if r.data:
            return dict(r.data[0])
    r2 = (
        client.table("factor_market_validation_panels")
        .select("*")
        .eq("cik", cik)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r2.data:
        return None
    return dict(r2.data[0])


def _fetch_snapshot_by_accession(
    client: Any, *, cik: str, accession_no: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_snapshots")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def _validation_context_summary(client: Any, universe_name: str) -> dict[str, Any]:
    """Latest completed validation runs — research context only (not features)."""
    out: dict[str, Any] = {"universe_name": universe_name, "summaries": []}
    for hz in ("next_month", "next_quarter"):
        rid = dbrec.fetch_latest_factor_validation_run_id(
            client, universe_name=universe_name, horizon_type=hz
        )
        if not rid:
            continue
        r = (
            client.table("factor_validation_summaries")
            .select(
                "factor_name,horizon_type,sample_count,spearman_rank_corr,pearson_corr,hit_rate_same_sign"
            )
            .eq("run_id", rid)
            .limit(12)
            .execute()
        )
        for row in r.data or []:
            out["summaries"].append(
                {
                    "horizon_type": hz,
                    "factor_name": row.get("factor_name"),
                    "sample_count": row.get("sample_count"),
                    "spearman_rank_corr": row.get("spearman_rank_corr"),
                    "pearson_corr": row.get("pearson_corr"),
                    "hit_rate_same_sign": row.get("hit_rate_same_sign"),
                }
            )
    return out


def build_harness_input_payload_v1(
    client: Any,
    *,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """
    Assemble HarnessInput v1. All numeric signal values come from deterministic tables.
    """
    cid = str(candidate["id"])
    run_id = str(candidate["run_id"])
    cik = str(candidate["cik"])
    as_of = str(candidate["as_of_date"])
    issuer_id = candidate.get("issuer_id")
    ticker = candidate.get("ticker")

    run = _fetch_run(client, run_id) or {}
    universe_name = str(run.get("universe_name") or "")
    factor_version = str(run.get("factor_version") or "v1")

    score = _fetch_score(client, run_id=run_id, cik=cik, as_of=as_of)
    components = _fetch_components(client, run_id=run_id, cik=cik, as_of=as_of)
    issuer = _fetch_issuer(client, str(issuer_id) if issuer_id else None)
    company_name = str(issuer.get("company_name") or ticker or cik) if issuer else str(
        ticker or cik
    )

    panel = _fetch_latest_factor_panel(client, cik)
    accession = str(panel.get("accession_no") or "") if panel else ""
    val_panel = _fetch_validation_panel(client, cik=cik, accession_no=accession or None)
    snapshot = (
        _fetch_snapshot_by_accession(client, cik=cik, accession_no=accession)
        if accession
        else None
    )

    key_factor_deltas: dict[str, Any] = {}
    if panel:
        for k in (
            "accruals",
            "gross_profitability",
            "asset_growth",
            "capex_intensity",
            "rnd_intensity",
            "financial_strength_score",
        ):
            if panel.get(k) is not None:
                key_factor_deltas[k] = panel.get(k)

    component_breakdown = [
        {
            "signal_name": c.get("signal_name"),
            "signal_family": c.get("signal_family"),
            "level_score": c.get("level_score"),
            "velocity_score": c.get("velocity_score"),
            "acceleration_score": c.get("acceleration_score"),
            "persistence_score": c.get("persistence_score"),
            "contamination_score": c.get("contamination_score"),
            "regime_fit_score": c.get("regime_fit_score"),
            "coverage_ratio": c.get("coverage_ratio"),
            "quality_flags_json": c.get("quality_flags_json"),
        }
        for c in components
    ]

    coverage_flags: list[str] = []
    missing_indicators: list[str] = []
    contamination_indicators: list[str] = []
    regime_flags: list[str] = []

    if score:
        if int(score.get("missing_component_count") or 0) > 0:
            missing_indicators.append("missing_components_in_score")
        mc = score.get("missing_component_count")
        coverage_flags.append(f"missing_component_count={mc}")
    else:
        missing_indicators.append("no_issuer_state_change_score_row")

    for c in components:
        qf = c.get("quality_flags_json") or {}
        if isinstance(qf, dict) and qf:
            coverage_flags.append(f"component_quality:{c.get('signal_name')}")

    filing_handles: list[dict[str, Any]] = []
    if accession:
        filing_handles.append(
            {
                "kind": "sec_accession",
                "accession_no": accession,
                "cik": cik,
            }
        )
    if snapshot:
        filing_handles.append(
            {
                "kind": "issuer_quarter_snapshot",
                "snapshot_id": str(snapshot.get("id")),
                "fiscal_year": snapshot.get("fiscal_year"),
                "fiscal_period": snapshot.get("fiscal_period"),
            }
        )

    val_ctx = {}
    if val_panel:
        val_ctx = {
            "signal_available_date": str(val_panel.get("signal_available_date") or ""),
            "panel_quality_flags": (val_panel.get("panel_json") or {}).get(
                "quality_flags", []
            )
            if isinstance(val_panel.get("panel_json"), dict)
            else [],
            "has_forward_return_fields": bool(
                val_panel.get("raw_return_1m") is not None
                or val_panel.get("raw_return_1q") is not None
            ),
        }
        # Labels only: forward fields exist for research panel join — not used as model features here.
        if val_ctx["has_forward_return_fields"]:
            coverage_flags.append("validation_panel_has_forward_return_columns_present")

    val_summary = _validation_context_summary(client, universe_name)

    payload: dict[str, Any] = {
        "contract_version": HARNESS_INPUT_CONTRACT_VERSION,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": cid,
        "issuer_id": str(issuer_id) if issuer_id else None,
        "ticker": ticker,
        "company_name": company_name,
        "as_of_date": as_of,
        "cik": cik,
        "state_change_run_id": run_id,
        "universe_name": universe_name,
        "factor_version": factor_version,
        "candidate_rank": candidate.get("candidate_rank"),
        "candidate_class": candidate.get("candidate_class"),
        "candidate_reason_json": candidate.get("candidate_reason_json"),
        "dominant_change_type": candidate.get("dominant_change_type"),
        "confidence_band": candidate.get("confidence_band"),
        "state_change_score": score.get("state_change_score_v1") if score else None,
        "state_change_direction": score.get("state_change_direction") if score else None,
        "score_gating_status": score.get("gating_status") if score else None,
        "top_driver_signals_json": score.get("top_driver_signals_json") if score else [],
        "component_breakdown": component_breakdown,
        "key_factor_deltas": key_factor_deltas,
        "validation_context_summary": val_summary,
        "validation_panel_join": val_ctx,
        "filing_source_handles": filing_handles,
        "coverage_flags": coverage_flags,
        "missing_data_indicators": missing_indicators,
        "contamination_indicators": contamination_indicators,
        "regime_context_flags": regime_flags,
    }
    payload["payload_hash"] = _json_hash(
        {k: v for k, v in payload.items() if k != "payload_hash"}
    )
    return payload


def materialize_inputs_for_run(
    client: Any,
    *,
    run_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    candidates = dbrec.fetch_state_change_candidates_for_run(
        client, run_id=run_id, limit=limit
    )
    built = 0
    errors: list[dict[str, Any]] = []
    for cand in candidates:
        try:
            payload = build_harness_input_payload_v1(client, candidate=cand)
            dbrec.upsert_ai_harness_candidate_input(
                client,
                candidate_id=str(cand["id"]),
                state_change_run_id=run_id,
                contract_version=HARNESS_INPUT_CONTRACT_VERSION,
                payload_json=payload,
                payload_hash=str(payload["payload_hash"]),
            )
            built += 1
        except Exception as ex:  # noqa: BLE001
            errors.append({"candidate_id": cand.get("id"), "error": str(ex)})
    return {"run_id": run_id, "inputs_built": built, "errors": errors}
