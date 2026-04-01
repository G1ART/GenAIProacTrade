from __future__ import annotations

import pytest

from sec.facts.concept_map import (
    CANONICAL_SOURCE_CONCEPTS,
    canonical_priority_for_concept,
    list_supported_canonicals,
    map_source_concept,
)


@pytest.mark.parametrize(
    "concept,expected,status",
    [
        ("us-gaap:NetIncomeLoss", "net_income", "mapped"),
        ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "revenue", "mapped"),
        ("us-gaap:Assets", "total_assets", "mapped"),
        ("us-gaap:NotARealTagForTests", None, "unmapped"),
    ],
)
def test_map_source_concept(concept: str, expected: str | None, status: str) -> None:
    c, st = map_source_concept(concept)
    assert st == status
    assert c == expected


def test_canonical_list_covers_work_order_minimums() -> None:
    keys = set(list_supported_canonicals())
    for k in (
        "revenue",
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "total_liabilities",
        "cash_and_equivalents",
        "research_and_development",
        "capex",
        "gross_profit",
        "shares_outstanding",
    ):
        assert k in keys
        assert CANONICAL_SOURCE_CONCEPTS[k]


def test_priority_us_gaap_revenue_variant() -> None:
    p_contract = canonical_priority_for_concept(
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    )
    p_legacy = canonical_priority_for_concept("us-gaap:Revenues")
    assert p_contract < p_legacy
