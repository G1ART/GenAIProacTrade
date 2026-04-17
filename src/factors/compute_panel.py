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
from factors.prior_period import (
    find_prior_snapshot,
    index_snapshots_by_period,
    normalize_fiscal_period,
)


_FLOW_CANONICAL_TO_COL = {
    "revenue": "revenue",
    "net_income": "net_income",
    "operating_cash_flow": "operating_cash_flow",
    "research_and_development": "research_and_development",
    "capex": "capex",
    "gross_profit": "gross_profit",
}

_PRIOR_QUARTER_FOR_YTD = {
    "Q2": "Q1",
    "Q3": "Q2",
    "Q4": "Q3",
}


def _period_sort_key(s: dict[str, Any]) -> tuple[int, int]:
    fy = int(s.get("fiscal_year") or 0)
    fp = normalize_fiscal_period(str(s.get("fiscal_period") or ""))
    order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}.get(fp, 99)
    return fy, order


def sort_snapshots_accounting_order(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(snapshots, key=_period_sort_key)


def _canonical_period_basis(snapshot: dict[str, Any], canonical: str) -> str:
    """snapshot_json.filled_canonicals[canon].period_basis — 기본값 "quarterly"."""
    snap_json = snapshot.get("snapshot_json") or {}
    filled = snap_json.get("filled_canonicals") or {}
    meta = filled.get(canonical) or {}
    return str(meta.get("period_basis") or "quarterly").lower()


def _ytd_to_qtd_effective(
    snapshot: dict[str, Any],
    snapshots_index: dict[tuple[int, str], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    flow canonical이 YTD 기준으로 저장된 경우 직전 분기 YTD를 빼서 QTD 유도.

    - Q1: YTD == QTD (3개월)이므로 변환 없음.
    - Q2/Q3/Q4: 직전 분기의 **같은 canonical YTD**를 차감.
    - FY: 연간 누적 그대로 유지 (Q4 분기값이 아니라 연간 팩터 해석).
    - prior가 YTD가 아니거나(=이미 QTD로 저장) prior 자체가 없으면 변환 skip.
    - basis가 "quarterly" 인 field는 건드리지 않음.

    반환: (effective_snapshot, adjustments_info)
    adjustments_info는 coverage/factor_json에 기록되는 진단 dict.
    """
    adjustments: dict[str, Any] = {}
    fy = snapshot.get("fiscal_year")
    fp_raw = snapshot.get("fiscal_period")
    fp = normalize_fiscal_period(str(fp_raw or ""))
    if fy is None or not fp:
        return dict(snapshot), adjustments
    if fp in ("Q1", "FY"):
        # Q1: YTD=QTD / FY: 연간 그대로
        return dict(snapshot), adjustments
    prior_fp = _PRIOR_QUARTER_FOR_YTD.get(fp)
    if prior_fp is None:
        return dict(snapshot), adjustments
    prior = snapshots_index.get((int(fy), prior_fp))

    prior_fp_norm = (
        normalize_fiscal_period(str(prior.get("fiscal_period") or "")) if prior else ""
    )
    # Q1 은 실제 측정 구간이 3개월이라 basis 태그와 무관하게 YTD(3M) 와 동일하다.
    # Q2 로의 subtraction chain에서는 Q1 값이 quarterly 로 저장돼 있어도 유효한
    # YTD 로 취급해야 한다 (그렇지 않으면 Q2 가 6M YTD OCF 를 그대로 써서 왜곡).
    prior_is_q1_implicit_ytd = prior_fp_norm == "Q1"

    adjusted = dict(snapshot)
    for canonical, col in _FLOW_CANONICAL_TO_COL.items():
        basis = _canonical_period_basis(snapshot, canonical)
        if basis != "ytd":
            continue
        cur_val = snapshot.get(col)
        if cur_val is None:
            continue
        if prior is None:
            adjustments[canonical] = {
                "action": "skipped",
                "reason": "prior_same_fy_quarter_missing",
                "current_basis": basis,
            }
            continue
        prior_basis = _canonical_period_basis(prior, canonical)
        prior_val = prior.get(col)
        prior_effective_ytd = prior_basis == "ytd" or prior_is_q1_implicit_ytd
        if not prior_effective_ytd or prior_val is None:
            adjustments[canonical] = {
                "action": "skipped",
                "reason": (
                    "prior_value_missing"
                    if prior_val is None
                    else "prior_not_ytd"
                ),
                "prior_basis": prior_basis,
                "prior_fiscal_period": prior_fp_norm,
            }
            continue
        try:
            qtd = float(cur_val) - float(prior_val)
        except (TypeError, ValueError):
            continue
        adjusted[col] = qtd
        adjustments[canonical] = {
            "action": "ytd_minus_prior_ytd",
            "current_ytd": float(cur_val),
            "prior_ytd": float(prior_val),
            "prior_basis": prior_basis,
            "prior_fiscal_period": prior_fp_norm,
            "prior_accession_no": prior.get("accession_no"),
            "qtd": qtd,
        }
    return adjusted, adjustments


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

    # flow canonical이 YTD 기준으로 저장된 경우 같은 FY의 직전 분기 YTD를 빼서
    # QTD로 변환한 effective snapshot을 factor 공식에 넘긴다. 이로써 AAPL/NVDA 10-Q
    # 같은 "OCF YTD만 보고" 발행사의 accruals 팩터도 계산 가능해진다.
    snapshots_by_fp = index_snapshots_by_period(all_snapshots)
    effective_current, ytd_adjustments = _ytd_to_qtd_effective(snapshot, snapshots_by_fp)

    acc, cov_acc, q_acc = compute_accruals(effective_current, prior)
    gp, cov_gp, q_gp = compute_gross_profitability(effective_current, prior)
    ag, cov_ag, q_ag = compute_asset_growth(effective_current, prior)
    ci, cov_ci, q_ci = compute_capex_intensity(effective_current, prior)
    ri, cov_ri, q_ri = compute_rnd_intensity(effective_current, prior)
    fs, cov_fs, q_fs = compute_financial_strength_score_v1(effective_current, prior)

    coverage_json = {
        "accruals": cov_acc,
        "gross_profitability": cov_gp,
        "asset_growth": cov_ag,
        "capex_intensity": cov_ci,
        "rnd_intensity": cov_ri,
        "financial_strength_score_v1": cov_fs,
        "prior_snapshot_found": prior is not None,
        "prior_accession_no": prior.get("accession_no") if prior else None,
        "period_basis_adjustments": ytd_adjustments,
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
