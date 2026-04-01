"""
단일 issuer_quarter_snapshots 행 → issuer_quarter_factor_panels 행 dict 조립.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from factors.formulas import (
    compute_accruals,
    compute_asset_growth,
    compute_capex_intensity,
    compute_financial_strength_score_v1,
    compute_gross_profitability,
    compute_rnd_intensity,
)
from factors.prior_period import find_prior_snapshot, normalize_fiscal_period


def _period_sort_key(s: dict[str, Any]) -> tuple[int, int]:
    fy = int(s.get("fiscal_year") or 0)
    fp = normalize_fiscal_period(str(s.get("fiscal_period") or ""))
    order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}.get(fp, 99)
    return fy, order


def sort_snapshots_accounting_order(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(snapshots, key=_period_sort_key)


def build_factor_panel_row(
    snapshot: dict[str, Any],
    all_snapshots: list[dict[str, Any]],
    *,
    factor_version: str,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    DB insert용 행 dict. prior는 all_snapshots에서 fiscal 체인으로 결정.
    """
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    prior = find_prior_snapshot(snapshot, all_snapshots)

    acc, cov_acc, q_acc = compute_accruals(snapshot, prior)
    gp, cov_gp, q_gp = compute_gross_profitability(snapshot, prior)
    ag, cov_ag, q_ag = compute_asset_growth(snapshot, prior)
    ci, cov_ci, q_ci = compute_capex_intensity(snapshot, prior)
    ri, cov_ri, q_ri = compute_rnd_intensity(snapshot, prior)
    fs, cov_fs, q_fs = compute_financial_strength_score_v1(snapshot, prior)

    coverage_json = {
        "accruals": cov_acc,
        "gross_profitability": cov_gp,
        "asset_growth": cov_ag,
        "capex_intensity": cov_ci,
        "rnd_intensity": cov_ri,
        "financial_strength_score_v1": cov_fs,
        "prior_snapshot_found": prior is not None,
        "prior_accession_no": prior.get("accession_no") if prior else None,
    }

    all_flags = list(
        dict.fromkeys(q_acc + q_gp + q_ag + q_ci + q_ri + q_fs)  # stable unique
    )
    quality_flags_json = {
        "flags": all_flags,
        "by_factor": {
            "accruals": q_acc,
            "gross_profitability": q_gp,
            "asset_growth": q_ag,
            "capex_intensity": q_ci,
            "rnd_intensity": q_ri,
            "financial_strength_score_v1": q_fs,
        },
    }

    factor_json = {
        "factor_version": factor_version,
        "accruals": {"value": acc},
        "gross_profitability": {"value": gp},
        "asset_growth": {"value": ag},
        "capex_intensity": {"value": ci},
        "rnd_intensity": {"value": ri},
        "financial_strength_score_v1": {
            "value": fs,
            "max_score_available": cov_fs.get("max_score_available"),
            "components": cov_fs.get("components"),
        },
    }

    sid = snapshot.get("id")
    return {
        "cik": snapshot["cik"],
        "fiscal_year": snapshot["fiscal_year"],
        "fiscal_period": snapshot["fiscal_period"],
        "accession_no": snapshot["accession_no"],
        "snapshot_id": str(sid) if sid else None,
        "factor_version": factor_version,
        "accruals": acc,
        "gross_profitability": gp,
        "asset_growth": ag,
        "capex_intensity": ci,
        "rnd_intensity": ri,
        "financial_strength_score": fs,
        "factor_json": factor_json,
        "coverage_json": coverage_json,
        "quality_flags_json": quality_flags_json,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
