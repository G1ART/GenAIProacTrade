"""
Canonical concept mapping v1 (us-gaap / dei 우선).

여러 source concept가 동일 canonical에 매핑될 수 있다.
매핑되지 않으면 (None, "unmapped") 반환.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# canonical -> 우선순위 높은 순서의 source concept (첫 일치가 스냅샷 우선 후보)
CANONICAL_SOURCE_CONCEPTS: dict[str, List[str]] = {
    "revenue": [
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:Revenues",
        "us-gaap:SalesRevenueNet",
        "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "net_income": [
        "us-gaap:NetIncomeLoss",
        "us-gaap:ProfitLoss",
    ],
    "operating_cash_flow": [
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
    ],
    "total_assets": [
        "us-gaap:Assets",
    ],
    "total_liabilities": [
        "us-gaap:Liabilities",
    ],
    "cash_and_equivalents": [
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "research_and_development": [
        "us-gaap:ResearchAndDevelopmentExpense",
    ],
    "capex": [
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
    ],
    "gross_profit": [
        "us-gaap:GrossProfit",
    ],
    "shares_outstanding": [
        "us-gaap:CommonStockSharesOutstanding",
        "dei:EntityCommonStockSharesOutstanding",
    ],
}

# 역인덱스: source_concept -> (canonical, priority rank lower = better)
_SOURCE_TO_CANONICAL: dict[str, Tuple[str, int]] = {}
for _canon, _sources in CANONICAL_SOURCE_CONCEPTS.items():
    for _rank, _sc in enumerate(_sources):
        # 더 앞선 canonical 리스트 순서가 우선
        if _sc not in _SOURCE_TO_CANONICAL or _rank < _SOURCE_TO_CANONICAL[_sc][1]:
            _SOURCE_TO_CANONICAL[_sc] = (_canon, _rank)


def map_source_concept(source_concept: str) -> Tuple[Optional[str], str]:
    """
    Returns:
        (canonical_concept or None, status)
        status: "mapped" | "unmapped"
    """
    if not source_concept or not isinstance(source_concept, str):
        return None, "unmapped"
    key = source_concept.strip()
    hit = _SOURCE_TO_CANONICAL.get(key)
    if hit:
        return hit[0], "mapped"
    return None, "unmapped"


def canonical_priority_for_concept(source_concept: str) -> int:
    """동일 canonical 후보 중 정렬용 (낮을수록 우선). 미매핑은 큰 값."""
    hit = _SOURCE_TO_CANONICAL.get((source_concept or "").strip())
    if not hit:
        return 9999
    return hit[1]


def list_supported_canonicals() -> list[str]:
    return list(CANONICAL_SOURCE_CONCEPTS.keys())
