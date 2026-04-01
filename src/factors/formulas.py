"""
회계 팩터 공식 v1 — README / schema_notes / definitions.py 와 동일 의미.

모든 함수는 (value | None, 해당 팩터 전용 coverage dict, quality flag 문자열 리스트) 반환.
"""

from __future__ import annotations

from typing import Any, Optional


def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def average_total_assets(
    current: dict[str, Any], prior: Optional[dict[str, Any]]
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """
    (total_assets_current + total_assets_prior) / 2.
    둘 중 하나라도 없거나 prior 없으면 None.
    """
    cov: dict[str, Any] = {
        "formula_used": "average_total_assets",
        "numerator_available": False,
        "denominator_available": False,
    }
    flags: list[str] = []
    ta_c = _f(current.get("total_assets"))
    if prior is None:
        flags.append("no_prior_snapshot")
        cov["prior_snapshot_found"] = False
        cov["missing_fields"] = ["prior_total_assets"]
        return None, cov, flags
    cov["prior_snapshot_found"] = True
    ta_p = _f(prior.get("total_assets"))
    cov["required_fields_present"] = {
        "total_assets_current": ta_c is not None,
        "total_assets_prior": ta_p is not None,
    }
    if ta_c is None or ta_p is None:
        missing = []
        if ta_c is None:
            missing.append("total_assets")
        if ta_p is None:
            missing.append("prior.total_assets")
        cov["missing_fields"] = missing
        flags.append("partial_inputs")
        return None, cov, flags
    avg = (ta_c + ta_p) / 2.0
    if avg == 0:
        flags.append("zero_denominator")
        cov["missing_fields"] = []
        return None, cov, flags
    cov["numerator_available"] = True
    cov["denominator_available"] = True
    cov["average_total_assets"] = avg
    return avg, cov, flags


def compute_accruals(
    current: dict[str, Any], prior: Optional[dict[str, Any]]
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """(net_income - operating_cash_flow) / average_total_assets"""
    ni = _f(current.get("net_income"))
    ocf = _f(current.get("operating_cash_flow"))
    flags: list[str] = []
    cov: dict[str, Any] = {"formula_used": "accruals_v1"}
    if ni is None or ocf is None:
        cov["missing_fields"] = [k for k, v in [("net_income", ni), ("operating_cash_flow", ocf)] if v is None]
        flags.append("partial_inputs")
        return None, cov, flags
    avg, subcov, subf = average_total_assets(current, prior)
    flags.extend(subf)
    cov["average_total_assets_detail"] = subcov
    if avg is None:
        cov["missing_fields"] = cov.get("missing_fields", []) + ["average_total_assets"]
        return None, cov, flags
    return (ni - ocf) / avg, cov, flags


def compute_gross_profitability(
    current: dict[str, Any], prior: Optional[dict[str, Any]]
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """gross_profit / average_total_assets"""
    gp = _f(current.get("gross_profit"))
    flags: list[str] = []
    cov: dict[str, Any] = {"formula_used": "gross_profitability_v1"}
    if gp is None:
        cov["missing_fields"] = ["gross_profit"]
        flags.append("partial_inputs")
        return None, cov, flags
    avg, subcov, subf = average_total_assets(current, prior)
    flags.extend(subf)
    cov["average_total_assets_detail"] = subcov
    if avg is None:
        return None, cov, flags
    return gp / avg, cov, flags


def compute_asset_growth(
    current: dict[str, Any], prior: Optional[dict[str, Any]]
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """(TA_t - TA_t-1) / TA_t-1 — prior는 직전 회계 분기 스냅샷."""
    cov: dict[str, Any] = {"formula_used": "asset_growth_v1"}
    flags: list[str] = []
    ta_c = _f(current.get("total_assets"))
    if prior is None:
        flags.append("no_prior_snapshot")
        cov["prior_snapshot_found"] = False
        return None, cov, flags
    cov["prior_snapshot_found"] = True
    ta_p = _f(prior.get("total_assets"))
    if ta_c is None or ta_p is None:
        cov["missing_fields"] = [
            x for x, y in [("total_assets", ta_c), ("prior.total_assets", ta_p)] if y is None
        ]
        flags.append("partial_inputs")
        return None, cov, flags
    if ta_p == 0:
        flags.append("zero_denominator")
        return None, cov, flags
    return (ta_c - ta_p) / ta_p, cov, flags


def compute_capex_intensity(
    current: dict[str, Any], prior: Optional[dict[str, Any]]
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """capex / average_total_assets (revenue 분모 사용 안 함, 고정)."""
    cx = _f(current.get("capex"))
    flags: list[str] = []
    cov: dict[str, Any] = {"formula_used": "capex_intensity_v1", "denominator": "average_total_assets"}
    if cx is None:
        cov["missing_fields"] = ["capex"]
        flags.append("partial_inputs")
        return None, cov, flags
    avg, subcov, subf = average_total_assets(current, prior)
    flags.extend(subf)
    cov["average_total_assets_detail"] = subcov
    if avg is None:
        return None, cov, flags
    if avg == 0:
        flags.append("zero_denominator")
        return None, cov, flags
    return cx / avg, cov, flags


def compute_rnd_intensity(
    current: dict[str, Any],
    _prior: Optional[dict[str, Any]],
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """research_and_development / revenue — revenue 없으면 null."""
    rnd = _f(current.get("research_and_development"))
    rev = _f(current.get("revenue"))
    cov: dict[str, Any] = {"formula_used": "rnd_intensity_v1", "denominator": "revenue"}
    flags: list[str] = []
    if rnd is None:
        cov["missing_fields"] = ["research_and_development"]
        flags.append("partial_inputs")
        return None, cov, flags
    if rev is None:
        cov["missing_fields"] = ["revenue"]
        flags.append("partial_inputs")
        return None, cov, flags
    if rev == 0:
        flags.append("zero_denominator")
        return None, cov, flags
    return rnd / rev, cov, flags


def compute_financial_strength_score_v1(
    current: dict[str, Any],
    prior: Optional[dict[str, Any]],
) -> tuple[Optional[float], dict[str, Any], list[str]]:
    """
    이진 구성요소 합산 점수. financial_strength_score 컬럼에는 actual_score 저장.
    max_score_available / components 는 factor_json에 병합됨.
    """
    flags: list[str] = []
    cov: dict[str, Any] = {"formula_used": "financial_strength_score_v1"}
    prior_eff = prior

    components: dict[str, Any] = {}
    points: list[int] = []
    available: list[str] = []

    ni = _f(current.get("net_income"))
    if ni is not None:
        available.append("net_income_positive")
        v = 1 if ni > 0 else 0
        points.append(v)
        components["net_income_positive"] = {"met": bool(ni > 0), "value": ni}
    else:
        components["net_income_positive"] = {"met": None, "reason": "missing_net_income"}

    ocf = _f(current.get("operating_cash_flow"))
    if ocf is not None:
        available.append("ocf_positive")
        points.append(1 if ocf > 0 else 0)
        components["ocf_positive"] = {"met": bool(ocf > 0), "value": ocf}
    else:
        components["ocf_positive"] = {"met": None, "reason": "missing_ocf"}

    if ocf is not None and ni is not None:
        available.append("ocf_ge_net_income")
        points.append(1 if ocf >= ni else 0)
        components["ocf_ge_net_income"] = {"met": bool(ocf >= ni), "ocf": ocf, "ni": ni}
    else:
        components["ocf_ge_net_income"] = {"met": None, "reason": "missing_ocf_or_ni"}

    gp = _f(current.get("gross_profit"))
    avg, _, subf = average_total_assets(current, prior_eff)
    flags.extend(subf)
    if gp is not None and avg is not None and avg != 0:
        gpr = gp / avg
        available.append("gross_profitability_positive")
        points.append(1 if gpr > 0 else 0)
        components["gross_profitability_positive"] = {"met": bool(gpr > 0), "gross_profitability": gpr}
    else:
        components["gross_profitability_positive"] = {
            "met": None,
            "reason": "missing_gross_profit_or_average_total_assets",
        }

    ta_c = _f(current.get("total_assets"))
    tl_c = _f(current.get("total_liabilities"))
    if prior_eff is not None:
        ta_p = _f(prior_eff.get("total_assets"))
        tl_p = _f(prior_eff.get("total_liabilities"))
    else:
        ta_p = tl_p = None

    if (
        prior_eff is not None
        and ta_c is not None
        and ta_c != 0
        and tl_c is not None
        and ta_p is not None
        and ta_p != 0
        and tl_p is not None
    ):
        lev_c = tl_c / ta_c
        lev_p = tl_p / ta_p
        available.append("leverage_improved")
        points.append(1 if lev_c < lev_p else 0)
        components["leverage_improved"] = {
            "met": bool(lev_c < lev_p),
            "leverage_current": lev_c,
            "leverage_prior": lev_p,
        }
    else:
        if prior_eff is None:
            flags.append("no_prior_snapshot")
        components["leverage_improved"] = {"met": None, "reason": "missing_prior_or_balance_sheet"}

    actual = float(sum(points))
    max_av = float(len(available))
    cov["max_score_available"] = max_av
    cov["actual_score"] = actual
    cov["components"] = components
    cov["prior_snapshot_found"] = prior_eff is not None

    return actual, cov, flags
