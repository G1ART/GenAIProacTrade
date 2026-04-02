"""
검증 대상 팩터 레지스트리 v1 — 문헌·매매 규칙이 아닌 메타데이터만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class ValidationFactorSpec:
    factor_name: str
    """DB `issuer_quarter_factor_panels` 컬럼명 (financial_strength_score_v1 → financial_strength_score)."""

    panel_column: str
    supported_horizons: Tuple[str, ...]
    preferred_direction_note: str
    requires_prior_snapshot: bool
    should_rank: bool
    include_in_quantiles: bool


VALIDATION_FACTORS_V1: tuple[ValidationFactorSpec, ...] = (
    ValidationFactorSpec(
        factor_name="accruals",
        panel_column="accruals",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="empirical only; literature often treats lower accruals as quality signal",
        requires_prior_snapshot=False,
        should_rank=True,
        include_in_quantiles=True,
    ),
    ValidationFactorSpec(
        factor_name="gross_profitability",
        panel_column="gross_profitability",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="higher may associate with stronger operating economics (descriptive only)",
        requires_prior_snapshot=False,
        should_rank=True,
        include_in_quantiles=True,
    ),
    ValidationFactorSpec(
        factor_name="asset_growth",
        panel_column="asset_growth",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="empirical only; growth vs returns context-dependent",
        requires_prior_snapshot=True,
        should_rank=True,
        include_in_quantiles=True,
    ),
    ValidationFactorSpec(
        factor_name="capex_intensity",
        panel_column="capex_intensity",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="empirical only",
        requires_prior_snapshot=False,
        should_rank=True,
        include_in_quantiles=True,
    ),
    ValidationFactorSpec(
        factor_name="rnd_intensity",
        panel_column="rnd_intensity",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="empirical only",
        requires_prior_snapshot=False,
        should_rank=True,
        include_in_quantiles=True,
    ),
    ValidationFactorSpec(
        factor_name="financial_strength_score_v1",
        panel_column="financial_strength_score",
        supported_horizons=("next_month", "next_quarter"),
        preferred_direction_note="higher = more binary quality flags satisfied (not Piotroski F-Score)",
        requires_prior_snapshot=True,
        should_rank=True,
        include_in_quantiles=True,
    ),
)


def get_factor_spec(name: str) -> ValidationFactorSpec | None:
    n = name.strip().lower()
    for s in VALIDATION_FACTORS_V1:
        if s.factor_name == n:
            return s
    return None


def list_factor_names() -> list[str]:
    return [s.factor_name for s in VALIDATION_FACTORS_V1]
