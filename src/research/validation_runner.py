"""
factor_market_validation_panels + issuer_quarter_factor_panels → Phase 5 검증 적재.
"""

from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from db.records import (
    factor_validation_run_finalize,
    factor_validation_run_insert_started,
    fetch_factor_market_validation_panels_for_symbols,
    fetch_issuer_quarter_factor_panels_for_accessions,
    issuer_quarter_factor_panel_join_key,
    insert_factor_coverage_report,
    insert_factor_quantile_result,
    insert_factor_validation_summary,
)
from research.metrics import (
    hit_rate_same_sign,
    ols_simple_slope_intercept,
    pearson_correlation,
    spearman_rank_correlation,
)
from research.quantiles import (
    bucket_descriptive_spread,
    build_quantile_buckets,
)
from research.standardize import winsorize, zscore
from research.summaries import aggregate_factor_coverage
from research.universe_slices import resolve_slice_symbols
from research.validation_registry import VALIDATION_FACTORS_V1

logger = logging.getLogger(__name__)

RUN_TYPE_DEFAULT = "factor_validation_research"

HORIZON_RETURN_KEYS = {
    "next_month": ("raw_return_1m", "excess_return_1m"),
    "next_quarter": ("raw_return_1q", "excess_return_1q"),
}


def _finite(x: Any) -> bool:
    if x is None:
        return False
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def _as_float(x: Any) -> Optional[float]:
    if not _finite(x):
        return None
    return float(x)


def run_factor_validation_research(
    client: Any,
    *,
    universe_name: str,
    horizon_type: str,
    factor_version: str = "v1",
    panel_limit: int = 8000,
    include_ols: bool = False,
    apply_winsorize: bool = False,
    n_quantiles: int = 5,
) -> dict[str, Any]:
    if horizon_type not in HORIZON_RETURN_KEYS:
        raise ValueError(f"horizon_type must be one of {list(HORIZON_RETURN_KEYS)}")

    raw_key, excess_key = HORIZON_RETURN_KEYS[horizon_type]
    symbols = resolve_slice_symbols(client, universe_name)
    vpanels = fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=panel_limit
    )
    accessions = sorted(
        {str(p["accession_no"]) for p in vpanels if p.get("accession_no")}
    )
    fp_map = fetch_issuer_quarter_factor_panels_for_accessions(
        client,
        accession_nos=accessions,
        limit_per_batch=max(panel_limit, 8000),
    )

    meta = {
        "symbol_count": len(symbols),
        "validation_panel_rows": len(vpanels),
        "factor_panel_keys": len(fp_map),
        "include_ols": include_ols,
        "apply_winsorize": apply_winsorize,
        "n_quantiles_preferred": n_quantiles,
    }
    target = len(VALIDATION_FACTORS_V1)
    run_id = factor_validation_run_insert_started(
        client,
        run_type=RUN_TYPE_DEFAULT,
        factor_version=factor_version,
        universe_name=universe_name,
        horizon_type=horizon_type,
        metadata_json=meta,
        target_count=target,
    )

    success_f = 0
    fail_f = 0
    errors: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    def fp_for(vp: dict[str, Any]) -> Optional[dict[str, Any]]:
        k = issuer_quarter_factor_panel_join_key(
            vp.get("cik"),
            vp.get("accession_no"),
            vp.get("factor_version"),
            default_factor_version=factor_version,
        )
        return fp_map.get(k)

    total_slice = len(vpanels)

    for spec in VALIDATION_FACTORS_V1:
        if horizon_type not in spec.supported_horizons:
            continue
        try:
            fp_rows_for_cov: list[dict[str, Any]] = []
            for vp in vpanels:
                fp = fp_for(vp)
                if fp is None:
                    fp_rows_for_cov.append(
                        {
                            spec.panel_column: None,
                            "coverage_json": {},
                            "quality_flags_json": {},
                        }
                    )
                else:
                    fp_rows_for_cov.append(fp)

            cov_agg = aggregate_factor_coverage(
                spec,
                fp_rows_for_cov,
                total_rows_in_slice=total_slice,
            )
            insert_factor_coverage_report(
                client,
                {
                    "run_id": run_id,
                    "factor_name": spec.factor_name,
                    "factor_version": factor_version,
                    "universe_name": universe_name,
                    "total_rows": cov_agg["total_rows"],
                    "available_rows": cov_agg["available_rows"],
                    "missing_rows": cov_agg["missing_rows"],
                    "missing_due_to_no_prior": cov_agg["missing_due_to_no_prior"],
                    "missing_due_to_zero_denominator": cov_agg[
                        "missing_due_to_zero_denominator"
                    ],
                    "missing_due_to_missing_fields": cov_agg[
                        "missing_due_to_missing_fields"
                    ],
                    "coverage_json": cov_agg["coverage_json"],
                    "created_at": now_iso,
                },
            )

            for return_basis, ret_list in (
                ("raw", [vp.get(raw_key) for vp in vpanels]),
                ("excess", [vp.get(excess_key) for vp in vpanels]),
            ):
                xs_f: list[float] = []
                ys: list[float] = []
                for i, vp in enumerate(vpanels):
                    fp = fp_for(vp)
                    fv = _as_float(fp.get(spec.panel_column) if fp else None)
                    rv = _as_float(ret_list[i])
                    if fv is None or rv is None:
                        continue
                    xs_f.append(fv)
                    ys.append(rv)

                if apply_winsorize and len(xs_f) >= 5:
                    xs_f = winsorize(xs_f)

                sample_count = len(vpanels)
                valid_n = len(xs_f)
                mean_f = statistics.mean(xs_f) if xs_f else None
                std_f = statistics.stdev(xs_f) if len(xs_f) > 1 else None
                mean_r = statistics.mean(ys) if ys else None
                std_r = statistics.stdev(ys) if len(ys) > 1 else None
                spear = spearman_rank_correlation(xs_f, ys)
                pear = pearson_correlation(xs_f, ys)
                hit = hit_rate_same_sign(xs_f, ys)

                summary_json: dict[str, Any] = {
                    "preferred_direction_note": spec.preferred_direction_note,
                    "should_rank": spec.should_rank,
                }
                if include_ols and len(xs_f) >= 3:
                    zx = zscore(xs_f)
                    zx_clean = [z for z in zx if z is not None]
                    if len(zx_clean) == len(xs_f):
                        ols_z = ols_simple_slope_intercept(zx_clean, ys)
                        if ols_z:
                            summary_json["ols_return_on_standardized_factor"] = ols_z
                    ols_raw = ols_simple_slope_intercept(xs_f, ys)
                    if ols_raw:
                        summary_json["ols_return_on_raw_factor"] = ols_raw

                insert_factor_validation_summary(
                    client,
                    {
                        "run_id": run_id,
                        "factor_name": spec.factor_name,
                        "factor_version": factor_version,
                        "universe_name": universe_name,
                        "horizon_type": horizon_type,
                        "return_basis": return_basis,
                        "sample_count": sample_count,
                        "valid_factor_count": valid_n,
                        "valid_return_count": valid_n,
                        "mean_factor": mean_f,
                        "std_factor": std_f,
                        "mean_return": mean_r,
                        "std_return": std_r,
                        "spearman_rank_corr": spear,
                        "pearson_corr": pear,
                        "hit_rate_same_sign": hit,
                        "summary_json": summary_json,
                        "created_at": now_iso,
                    },
                )

            # 분위: 유효 (factor, raw, excess) 동시 유한인 행만
            q_f: list[float] = []
            q_raw: list[float] = []
            q_ex: list[float] = []
            for vp in vpanels:
                fp = fp_for(vp)
                fv = _as_float(fp.get(spec.panel_column) if fp else None)
                rr = _as_float(vp.get(raw_key))
                er = _as_float(vp.get(excess_key))
                if fv is None or rr is None or er is None:
                    continue
                q_f.append(fv)
                q_raw.append(rr)
                q_ex.append(er)

            if apply_winsorize and len(q_f) >= 5:
                q_f = winsorize(q_f)

            buckets, qmeta = build_quantile_buckets(q_f, q_raw, q_ex, n_quantiles=n_quantiles)
            if buckets:
                for return_basis in ("raw", "excess"):
                    spread_info = bucket_descriptive_spread(buckets, return_basis=return_basis)
                    for b in buckets:
                        insert_factor_quantile_result(
                            client,
                            {
                                "run_id": run_id,
                                "factor_name": spec.factor_name,
                                "factor_version": factor_version,
                                "universe_name": universe_name,
                                "horizon_type": horizon_type,
                                "return_basis": return_basis,
                                "quantile_index": b.quantile_index,
                                "quantile_count": len(b.indices),
                                "avg_factor_value": statistics.mean(b.factors)
                                if b.factors
                                else None,
                                "avg_raw_return": statistics.mean(b.raw_returns)
                                if b.raw_returns
                                else None,
                                "avg_excess_return": statistics.mean(b.excess_returns)
                                if b.excess_returns
                                else None,
                                "median_raw_return": statistics.median(b.raw_returns)
                                if b.raw_returns
                                else None,
                                "median_excess_return": statistics.median(b.excess_returns)
                                if b.excess_returns
                                else None,
                                "result_json": {
                                    "quantile_meta": qmeta,
                                    "descriptive_spread": spread_info,
                                },
                                "created_at": now_iso,
                            },
                        )
            success_f += 1
        except Exception as ex:  # noqa: BLE001
            fail_f += 1
            errors.append({"factor": spec.factor_name, "error": str(ex)})
            logger.exception("factor validation 실패 %s", spec.factor_name)

    status = "completed" if success_f > 0 else "failed"
    factor_validation_run_finalize(
        client,
        run_id=run_id,
        status=status,
        success_count=success_f,
        failure_count=fail_f,
        error_json={"errors": errors} if errors else None,
    )
    return {
        "run_id": run_id,
        "status": status,
        "universe_name": universe_name,
        "horizon_type": horizon_type,
        "validation_panels_used": total_slice,
        "symbols_in_slice": len(symbols),
        "factors_ok": success_f,
        "factors_failed": fail_f,
        "errors": errors,
    }
