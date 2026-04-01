"""
Factor definitions registry v1 — 명시적·해석 가능한 고정 정의만 (자동 팩터 생성 없음).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class FactorDefinition:
    factor_name: str
    formula_description: str
    required_fields: FrozenSet[str]
    optional_fields: FrozenSet[str]
    interpretation_note: str
    version: str


FACTOR_DEFINITIONS_V1: dict[str, FactorDefinition] = {
    "accruals": FactorDefinition(
        factor_name="accruals",
        formula_description="(net_income - operating_cash_flow) / average_total_assets",
        required_fields=frozenset({"net_income", "operating_cash_flow"}),
        optional_fields=frozenset({"total_assets"}),
        interpretation_note="이익 대비 운영현금흐름 차이를 평균 총자산으로 스케일. prior 분기 total_assets 없으면 평균 불가 → null.",
        version="v1",
    ),
    "gross_profitability": FactorDefinition(
        factor_name="gross_profitability",
        formula_description="gross_profit / average_total_assets",
        required_fields=frozenset({"gross_profit"}),
        optional_fields=frozenset({"total_assets"}),
        interpretation_note="매출총이익 대비 평균 총자산. 평균 총자산 산출 불가 시 null.",
        version="v1",
    ),
    "asset_growth": FactorDefinition(
        factor_name="asset_growth",
        formula_description="(total_assets_t - total_assets_t_minus_1) / total_assets_t_minus_1",
        required_fields=frozenset({"total_assets"}),
        optional_fields=frozenset(),
        interpretation_note="직전 회계 분기 스냅샷의 total_assets 필수. 분모 0이면 null + 플래그.",
        version="v1",
    ),
    "capex_intensity": FactorDefinition(
        factor_name="capex_intensity",
        formula_description="capex / average_total_assets (고정; revenue 분모 미사용)",
        required_fields=frozenset({"capex"}),
        optional_fields=frozenset({"total_assets"}),
        interpretation_note="CAPEX를 평균 총자산으로 나눔. 평균 불가 시 null.",
        version="v1",
    ),
    "rnd_intensity": FactorDefinition(
        factor_name="rnd_intensity",
        formula_description="research_and_development / revenue",
        required_fields=frozenset({"research_and_development"}),
        optional_fields=frozenset({"revenue"}),
        interpretation_note="매출이 없으면 null. 대체 분모 사용 안 함.",
        version="v1",
    ),
    "financial_strength_score_v1": FactorDefinition(
        factor_name="financial_strength_score_v1",
        formula_description=(
            "가중 이진 합산: NI>0, OCF>0, OCF>=NI, gross_profitability>0, "
            "leverage(L/A) 개선(prior 대비). 사용 가능한 항목만 점수에 포함."
        ),
        required_fields=frozenset(),
        optional_fields=frozenset(
            {
                "net_income",
                "operating_cash_flow",
                "gross_profit",
                "total_assets",
                "total_liabilities",
            }
        ),
        interpretation_note=(
            "Piotroski 전체가 아닌 snapshot 범위 내 결정적 composite. "
            "max_score_available / actual_score는 factor_json에 기록."
        ),
        version="v1",
    ),
}


def list_factor_names_v1() -> list[str]:
    return list(FACTOR_DEFINITIONS_V1.keys())
