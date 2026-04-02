"""
신호별 방향·변환 규칙 — 실행/알파 언어 없음.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

PreferredDirection = Literal["higher_is_positive", "lower_is_positive", "context_dependent"]
LevelMethod = Literal["cross_section_z", "raw_only"]
VelocityMethod = Literal["first_difference", "pct_change_nullable"]
AccelerationMethod = Literal["delta_of_delta"]
PersistenceMethod = Literal["same_sign_streak", "threshold_hold_ratio", "rolling_direction_consistency"]


@dataclass(frozen=True)
class StateChangeSignalSpec:
    signal_name: str
    source_column: str
    """issuer_quarter_factor_panels 컬럼명."""
    preferred_direction: PreferredDirection
    level_method: LevelMethod
    velocity_method: VelocityMethod
    acceleration_method: AccelerationMethod
    persistence_method: PersistenceMethod
    min_history_required: int
    winsorize_policy_nullable: Optional[str]
    notes: str


STATE_CHANGE_SIGNALS_V1: tuple[StateChangeSignalSpec, ...] = (
    StateChangeSignalSpec(
        signal_name="accruals",
        source_column="accruals",
        preferred_direction="context_dependent",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=2,
        winsorize_policy_nullable="optional_1_99_if_enabled",
        notes="문헌적으로 낮은 accrual이 품질과 연관되는 경우가 많으나 맥락 의존; level 은 z만, 방향 해석은 보수적.",
    ),
    StateChangeSignalSpec(
        signal_name="gross_profitability",
        source_column="gross_profitability",
        preferred_direction="higher_is_positive",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=2,
        winsorize_policy_nullable=None,
        notes="수익성 수준 상승을 긍정 방향으로 정렬(기술적 메타).",
    ),
    StateChangeSignalSpec(
        signal_name="asset_growth",
        source_column="asset_growth",
        preferred_direction="context_dependent",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=3,
        winsorize_policy_nullable=None,
        notes="prior 스냅샷 필요 팩터; 성장 vs 수익은 맥락 의존.",
    ),
    StateChangeSignalSpec(
        signal_name="capex_intensity",
        source_column="capex_intensity",
        preferred_direction="context_dependent",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=2,
        winsorize_policy_nullable=None,
        notes="CapEx 강도; 산업·주기 민감.",
    ),
    StateChangeSignalSpec(
        signal_name="rnd_intensity",
        source_column="rnd_intensity",
        preferred_direction="context_dependent",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=2,
        winsorize_policy_nullable=None,
        notes="R&D 강도; 섹터 편향.",
    ),
    StateChangeSignalSpec(
        signal_name="financial_strength_score_v1",
        source_column="financial_strength_score",
        preferred_direction="higher_is_positive",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=3,
        winsorize_policy_nullable=None,
        notes="DB 컬럼 financial_strength_score; 이진 플래그 합성 점수.",
    ),
)


def get_signal_spec(name: str) -> StateChangeSignalSpec | None:
    n = name.strip().lower().replace("-", "_")
    for s in STATE_CHANGE_SIGNALS_V1:
        if s.signal_name == n:
            return s
    return None
