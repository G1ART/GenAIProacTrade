"""
State change 실행기 — factor_market_validation_panels 미조회·미사용.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from db import records as dbrec
from state_change import CONFIG_VERSION_STATE_CHANGE_V1
from state_change.candidates import (
    IssuerDateScoreRow,
    classify_candidate,
    dominant_change_type,
)
from state_change.components import (
    apply_direction_delta,
    apply_direction_level,
    contamination_placeholder,
    coverage_ratio_for_signal,
    persistence_score,
    regime_fit_from_risk_free,
)
from state_change.loaders import (
    load_factor_panels_for_cik,
    load_issuers_for_universe_symbols,
    load_risk_free_rates_window,
    load_snapshots_for_ids,
)
from state_change.scoring import (
    SubScoreParts,
    confidence_band,
    direction_from_score,
    gating_status,
    population_zscores,
    resolve_component_weights,
    top_drivers,
    weighted_composite,
)
from state_change.signal_registry import STATE_CHANGE_SIGNALS_V1, StateChangeSignalSpec
from state_change.transforms import (
    as_float,
    as_of_date_for_panel,
    build_lag_series,
    ordered_panels_for_cik,
)
from state_change.universe_scope import assert_known_universe, resolve_universe_symbols

logger = logging.getLogger(__name__)

RUN_TYPE = "state_change_engine_v1"


def _date_minus_days(iso_date: str, days: int) -> str:
    d = datetime.fromisoformat(iso_date[:10])
    return (d - timedelta(days=days)).date().isoformat()


def _build_z_maps(
    observations: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str, str], Optional[float]],
    dict[tuple[str, str, str], Optional[float]],
    dict[tuple[str, str, str], Optional[float]],
]:
    level_b: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    vel_b: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    acc_b: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)

    for obs in observations:
        ordered = obs["ordered"]
        idx = obs["idx"]
        as_of = obs["as_of_date"]
        cik = obs["cik"]
        for spec in STATE_CHANGE_SIGNALS_V1:
            col = spec.source_column
            vals = [as_float(p.get(col)) for p in ordered]
            ls = build_lag_series(vals, idx)
            key = (as_of, spec.signal_name)
            if ls.current is not None:
                level_b[key].append((cik, ls.current))
            if ls.velocity is not None:
                vel_b[key].append((cik, ls.velocity))
            if ls.acceleration is not None:
                acc_b[key].append((cik, ls.acceleration))

    def assign(
        buckets: dict[tuple[str, str], list[tuple[str, float]]],
    ) -> dict[tuple[str, str, str], Optional[float]]:
        out: dict[tuple[str, str, str], Optional[float]] = {}
        for (d, sig), pairs in buckets.items():
            ciks = [c for c, _ in pairs]
            vs = [v for _, v in pairs]
            zs = population_zscores(vs)
            if zs is None:
                for cik in ciks:
                    out[(cik, d, sig)] = None
            else:
                for cik, z in zip(ciks, zs):
                    out[(cik, d, sig)] = z
        return out

    return assign(level_b), assign(vel_b), assign(acc_b)


def _one_component_row(
    *,
    run_id: str,
    universe_name: str,
    factor_version: str,
    obs: dict[str, Any],
    spec: StateChangeSignalSpec,
    z_lvl: dict[tuple[str, str, str], Optional[float]],
    z_vel: dict[tuple[str, str, str], Optional[float]],
    z_acc: dict[tuple[str, str, str], Optional[float]],
    regime_score: Optional[float],
    include_overlays: bool,
    now_iso: str,
) -> dict[str, Any]:
    cik = obs["cik"]
    as_of = obs["as_of_date"]
    ordered = obs["ordered"]
    idx = obs["idx"]
    panel = obs["panel"]
    col = spec.source_column
    vals = [as_float(p.get(col)) for p in ordered]
    ls = build_lag_series(vals, idx)

    zl = z_lvl.get((cik, as_of, spec.signal_name))
    zv = z_vel.get((cik, as_of, spec.signal_name))
    za = z_acc.get((cik, as_of, spec.signal_name))

    level_s = apply_direction_level(zl, spec) if zl is not None else None
    velocity_s = apply_direction_delta(zv, spec) if zv is not None else None
    acceleration_s = apply_direction_delta(za, spec) if za is not None else None
    pers_s = persistence_score(ls.vel_history)

    cont_s, cont_notes = contamination_placeholder(include_overlays)
    has_reg = regime_score is not None
    weights = resolve_component_weights(
        has_contamination=cont_s is not None, has_regime=has_reg
    )
    parts = SubScoreParts(
        level=level_s,
        velocity=velocity_s,
        acceleration=acceleration_s,
        persistence=pers_s,
        contamination=cont_s,
        regime_fit=regime_score,
    )
    _, den, inc = weighted_composite(parts, base_weights=weights)

    qflags: list[str] = []
    if spec.preferred_direction == "context_dependent":
        qflags.append("context_dependent_signal")
    notes: dict[str, Any] = {
        "weighted_composite_denominator": den,
        "included_axes": inc,
        "contamination": cont_notes,
    }

    cov = coverage_ratio_for_signal(panel, spec.signal_name)

    return {
        "run_id": run_id,
        "issuer_id": obs.get("issuer_id"),
        "cik": cik,
        "ticker": obs.get("ticker"),
        "as_of_date": as_of,
        "universe_name": universe_name,
        "signal_family": "accounting_factor",
        "signal_name": spec.signal_name,
        "current_value": ls.current,
        "lag_1_value": ls.lag_1,
        "lag_2_value": ls.lag_2,
        "lag_4_value": ls.lag_4,
        "level_score": level_s,
        "velocity_score": velocity_s,
        "acceleration_score": acceleration_s,
        "persistence_score": pers_s,
        "contamination_score": cont_s,
        "regime_fit_score": regime_score,
        "coverage_ratio": cov,
        "quality_flags_json": {"flags": qflags},
        "notes_json": notes,
        "created_at": now_iso,
    }


def run_state_change(
    client: Any,
    *,
    universe_name: str,
    factor_version: str = "v1",
    as_of_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    dry_run: bool = False,
    include_nullable_overlays: bool = False,
) -> dict[str, Any]:
    assert_known_universe(universe_name)
    symbols = resolve_universe_symbols(client, universe_name)
    issuers = load_issuers_for_universe_symbols(
        client, symbols, max_issuers=max(1, limit)
    )

    observations: list[dict[str, Any]] = []
    warnings = 0

    for iss in issuers:
        cik = str(iss["cik"])
        ticker = str(iss.get("ticker") or "").upper().strip() or None
        iid = str(iss["id"])
        panels = load_factor_panels_for_cik(client, cik=cik, factor_version=factor_version)
        if not panels:
            warnings += 1
            continue
        ordered = ordered_panels_for_cik(panels)
        snap_ids = [str(p["snapshot_id"]) for p in ordered if p.get("snapshot_id")]
        snaps = load_snapshots_for_ids(client, snap_ids)
        for idx, panel in enumerate(ordered):
            sid = panel.get("snapshot_id")
            snap = snaps.get(str(sid)) if sid else None
            as_of = as_of_date_for_panel(panel, snap)
            if as_of_date and as_of != as_of_date:
                continue
            if start_date and as_of < start_date:
                continue
            if end_date and as_of > end_date:
                continue
            observations.append(
                {
                    "issuer_id": iid,
                    "cik": cik,
                    "ticker": ticker,
                    "as_of_date": as_of,
                    "panel": panel,
                    "idx": idx,
                    "ordered": ordered,
                }
            )

    if not observations:
        return {
            "run_id": None,
            "status": "completed",
            "observations": 0,
            "warnings": warnings,
            "dry_run": dry_run,
            "message": "no_observations_after_filters",
        }

    # 동일 (cik, as_of_date) 는 시계열 상 가장 최신 분기(큰 idx) 하나만 유지 → 유니크 제약·중복 점수 방지
    best_obs: dict[tuple[str, str], dict[str, Any]] = {}
    for ob in observations:
        k = (ob["cik"], ob["as_of_date"])
        if k not in best_obs or ob["idx"] > best_obs[k]["idx"]:
            best_obs[k] = ob
    observations = sorted(best_obs.values(), key=lambda x: (x["cik"], x["as_of_date"]))

    dates = sorted({o["as_of_date"] for o in observations})
    rf_start = _date_minus_days(dates[-1], 800)
    all_rates = load_risk_free_rates_window(
        client, start_date=rf_start, end_date=dates[-1]
    )
    regime_by_date: dict[str, tuple[Optional[float], dict[str, Any]]] = {}
    for d in dates:
        filt = [r for r in all_rates if str(r.get("rate_date", ""))[:10] <= d]
        rs, meta = regime_fit_from_risk_free(
            filt, as_of_date=d, include_overlay=include_nullable_overlays
        )
        regime_by_date[d] = (rs, meta)

    z_lvl, z_vel, z_acc = _build_z_maps(observations)

    now_iso = datetime.now(timezone.utc).isoformat()
    input_snapshot = {
        "universe_name": universe_name,
        "factor_version": factor_version,
        "config_version": CONFIG_VERSION_STATE_CHANGE_V1,
        "issuer_limit": limit,
        "observation_count": len(observations),
        "as_of_filter": as_of_date,
        "start_date": start_date,
        "end_date": end_date,
        "signals": [s.signal_name for s in STATE_CHANGE_SIGNALS_V1],
    }

    run_id: Optional[str] = None
    if not dry_run:
        run_id = dbrec.state_change_run_insert_started(
            client,
            run_type=RUN_TYPE,
            universe_name=universe_name,
            as_of_date_start=start_date or dates[0],
            as_of_date_end=end_date or dates[-1],
            factor_version=factor_version,
            config_version=CONFIG_VERSION_STATE_CHANGE_V1,
            input_snapshot_json=input_snapshot,
        )

    component_rows: list[dict[str, Any]] = []
    contrib_by_issuer_date: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(
        list
    )
    weight_den_by_issuer_date: dict[tuple[str, str], list[float]] = defaultdict(list)
    missing_slots_by_issuer_date: dict[tuple[str, str], int] = defaultdict(int)
    total_slots_by_issuer_date: dict[tuple[str, str], int] = defaultdict(int)
    cov_sum_by_issuer_date: dict[tuple[str, str], float] = defaultdict(float)
    cov_n_by_issuer_date: dict[tuple[str, str], int] = defaultdict(int)

    for obs in observations:
        as_of = obs["as_of_date"]
        regime_score = regime_by_date[as_of][0]
        cik = obs["cik"]
        key = (cik, as_of)
        for spec in STATE_CHANGE_SIGNALS_V1:
            row = _one_component_row(
                run_id=run_id or "00000000-0000-0000-0000-000000000000",
                universe_name=universe_name,
                factor_version=factor_version,
                obs=obs,
                spec=spec,
                z_lvl=z_lvl,
                z_vel=z_vel,
                z_acc=z_acc,
                regime_score=regime_score,
                include_overlays=include_nullable_overlays,
                now_iso=now_iso,
            )
            component_rows.append(row)

            notes = row["notes_json"]
            den = float(notes.get("weighted_composite_denominator") or 0)
            inc = list(notes.get("included_axes") or [])
            base_inc = [x for x in inc if x in ("level", "velocity", "acceleration", "persistence")]
            total_slots_by_issuer_date[key] += 4
            missing_slots_by_issuer_date[key] += 4 - len(base_inc)
            if den > 0:
                parts = SubScoreParts(
                    level=row["level_score"],
                    velocity=row["velocity_score"],
                    acceleration=row["acceleration_score"],
                    persistence=row["persistence_score"],
                    contamination=row["contamination_score"],
                    regime_fit=row["regime_fit_score"],
                )
                w = resolve_component_weights(
                    has_contamination=row["contamination_score"] is not None,
                    has_regime=row["regime_fit_score"] is not None,
                )
                sub, comp_den, _ = weighted_composite(parts, base_weights=w)
                if comp_den > 0:
                    contrib_by_issuer_date[key].append((spec.signal_name, sub))
                    weight_den_by_issuer_date[key].append(float(comp_den))
            cov_sum_by_issuer_date[key] += float(row["coverage_ratio"] or 0)
            cov_n_by_issuer_date[key] += 1

    score_rows: list[dict[str, Any]] = []
    candidate_input: list[IssuerDateScoreRow] = []

    for obs in observations:
        cik = obs["cik"]
        as_of = obs["as_of_date"]
        key = (cik, as_of)
        contribs = contrib_by_issuer_date[key]
        if not contribs:
            iss_score = 0.0
        else:
            iss_score = statistics.mean([c for _, c in contribs])

        direction = direction_from_score(iss_score)
        cn = cov_n_by_issuer_date[key] or 1
        cov_avg = cov_sum_by_issuer_date[key] / cn
        ms = missing_slots_by_issuer_date[key]
        ts = total_slots_by_issuer_date[key]
        inc_n = len(contribs)
        dens = weight_den_by_issuer_date[key]
        norm_ws = (
            round(statistics.mean(dens), 8) if dens else None
        )
        conf = confidence_band(
            included=inc_n,
            missing=ms,
            coverage_avg=cov_avg,
        )
        gate = gating_status(
            missing_component_count=ms,
            coverage_avg=cov_avg,
            min_signals=1,
            signals_with_data=inc_n,
        )
        drivers = top_drivers([(a, b) for a, b in contribs], k=5)
        wjson: list[str] = []
        if ms > ts * 0.5:
            wjson.append("high_missing_axes")

        sr = {
            "run_id": run_id or "00000000-0000-0000-0000-000000000000",
            "issuer_id": obs["issuer_id"],
            "cik": cik,
            "ticker": obs["ticker"],
            "as_of_date": as_of,
            "universe_name": universe_name,
            "state_change_score_v1": round(iss_score, 8),
            "state_change_direction": direction,
            "confidence_band": conf,
            "included_component_count": inc_n,
            "missing_component_count": ms,
            "normalized_weight_sum": norm_ws,
            "gating_status": gate,
            "top_driver_signals_json": drivers,
            "warnings_json": wjson,
            "created_at": now_iso,
        }
        score_rows.append(sr)
        candidate_input.append(
            IssuerDateScoreRow(
                cik=cik,
                ticker=obs.get("ticker"),
                as_of_date=as_of,
                score=iss_score,
                direction=direction,
                confidence_band=conf,
                gating_status=gate,
                missing_component_count=ms,
                included_component_count=inc_n,
            )
        )

    ranked = sorted(
        candidate_input,
        key=lambda r: (abs(r.score), r.as_of_date, r.cik),
        reverse=True,
    )
    issuer_id_by_key = {
        (o["cik"], o["as_of_date"]): o.get("issuer_id") for o in observations
    }
    cand_rows: list[dict[str, Any]] = []
    for i, row in enumerate(ranked, start=1):
        cls, reason, excl, pri = classify_candidate(
            row, rank=i, total_ranked=len(ranked)
        )
        cand_rows.append(
            {
                "run_id": run_id or "00000000-0000-0000-0000-000000000000",
                "issuer_id": issuer_id_by_key.get((row.cik, row.as_of_date)),
                "cik": row.cik,
                "ticker": row.ticker,
                "as_of_date": row.as_of_date,
                "candidate_rank": i,
                "candidate_class": cls,
                "candidate_reason_json": reason,
                "dominant_change_type": dominant_change_type(row.direction),
                "confidence_band": row.confidence_band,
                "human_review_priority": pri,
                "excluded_reason": excl,
                "created_at": now_iso,
            }
        )

    if dry_run:
        return {
            "run_id": None,
            "status": "dry_run",
            "components": len(component_rows),
            "scores": len(score_rows),
            "candidates": len(cand_rows),
            "warnings": warnings,
            "sample_scores": score_rows[:5],
            "sample_candidates": cand_rows[:5],
        }

    assert run_id is not None
    for r in component_rows:
        r["run_id"] = run_id
    for r in score_rows:
        r["run_id"] = run_id
    for r in cand_rows:
        r["run_id"] = run_id

    try:
        dbrec.insert_state_change_components_batch(client, component_rows)
        dbrec.insert_state_change_scores_batch(client, score_rows)
        dbrec.insert_state_change_candidates_batch(client, cand_rows)
        dbrec.state_change_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            row_count=len(component_rows) + len(score_rows) + len(cand_rows),
            warning_count=warnings,
        )
    except Exception as e:
        logger.exception("state_change run failed")
        dbrec.state_change_run_finalize(
            client,
            run_id=run_id,
            status="failed",
            row_count=0,
            warning_count=warnings,
            error_json={"error": str(e)},
        )
        raise

    return {
        "run_id": run_id,
        "status": "completed",
        "components_written": len(component_rows),
        "scores_written": len(score_rows),
        "candidates_written": len(cand_rows),
        "warnings": warnings,
    }
