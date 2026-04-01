from __future__ import annotations

from factors.formulas import (
    average_total_assets,
    compute_accruals,
    compute_asset_growth,
    compute_capex_intensity,
    compute_financial_strength_score_v1,
    compute_gross_profitability,
    compute_rnd_intensity,
)


def test_average_total_assets() -> None:
    cur = {"total_assets": 200.0}
    prior = {"total_assets": 100.0}
    avg, cov, flags = average_total_assets(cur, prior)
    assert avg == 150.0
    assert "no_prior_snapshot" not in flags


def test_average_total_assets_no_prior() -> None:
    avg, _cov, flags = average_total_assets({"total_assets": 1.0}, None)
    assert avg is None
    assert "no_prior_snapshot" in flags


def test_accruals() -> None:
    cur = {"net_income": 100.0, "operating_cash_flow": 40.0, "total_assets": 200.0}
    prior = {"total_assets": 100.0}
    v, _c, _f = compute_accruals(cur, prior)
    assert v is not None
    assert abs(v - (60.0 / 150.0)) < 1e-9


def test_gross_profitability() -> None:
    cur = {"gross_profit": 300.0, "total_assets": 200.0}
    prior = {"total_assets": 100.0}
    v, _, _ = compute_gross_profitability(cur, prior)
    assert v == 300.0 / 150.0


def test_asset_growth() -> None:
    cur = {"total_assets": 120.0}
    prior = {"total_assets": 100.0}
    v, _, f = compute_asset_growth(cur, prior)
    assert v == 0.2
    assert "no_prior_snapshot" not in f


def test_asset_growth_zero_denominator() -> None:
    cur = {"total_assets": 100.0}
    prior = {"total_assets": 0.0}
    v, _, f = compute_asset_growth(cur, prior)
    assert v is None
    assert "zero_denominator" in f


def test_capex_intensity() -> None:
    cur = {"capex": 15.0, "total_assets": 200.0}
    prior = {"total_assets": 100.0}
    v, cov, _ = compute_capex_intensity(cur, prior)
    assert v == 15.0 / 150.0
    assert cov.get("denominator") == "average_total_assets"


def test_rnd_intensity() -> None:
    cur = {"research_and_development": 10.0, "revenue": 100.0}
    v, cov, _ = compute_rnd_intensity(cur, None)
    assert v == 0.1
    assert cov.get("denominator") == "revenue"


def test_rnd_intensity_no_revenue() -> None:
    cur = {"research_and_development": 10.0}
    v, _, f = compute_rnd_intensity(cur, None)
    assert v is None
    assert "partial_inputs" in f


def test_financial_strength_basic() -> None:
    cur = {
        "net_income": 10.0,
        "operating_cash_flow": 20.0,
        "gross_profit": 50.0,
        "total_assets": 200.0,
        "total_liabilities": 80.0,
    }
    prior = {
        "total_assets": 200.0,
        "total_liabilities": 100.0,
    }
    score, cov, _ = compute_financial_strength_score_v1(cur, prior)
    assert score is not None
    assert cov["max_score_available"] >= 1
    assert "components" in cov
