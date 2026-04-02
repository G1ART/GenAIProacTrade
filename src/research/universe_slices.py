"""
검증용 universe slice — Phase 4 유니버스 멤버십 기준 결정적 집합.
"""

from __future__ import annotations

from typing import Any

# README·코드 공통 상수
UNIVERSE_SP500_CURRENT = "sp500_current"
UNIVERSE_PROXY_CANDIDATES = "sp500_proxy_candidates_v1"
UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1 = "combined_largecap_research_v1"

ALL_RESEARCH_SLICES = (
    UNIVERSE_SP500_CURRENT,
    UNIVERSE_PROXY_CANDIDATES,
    UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1,
)


def _latest_symbols_for_universe(client: Any, universe_name: str) -> list[str]:
    r = (
        client.table("universe_memberships")
        .select("symbol,as_of_date")
        .eq("universe_name", universe_name)
        .execute()
    )
    rows = r.data or []
    if not rows:
        return []
    max_d = max(str(row["as_of_date"]) for row in rows)
    syms = sorted(
        {str(row["symbol"]).upper().strip() for row in rows if str(row["as_of_date"]) == max_d}
    )
    return syms


def resolve_slice_symbols(client: Any, universe_name: str) -> list[str]:
    """
    universe_name 에 해당하는 검증 심볼 집합(대문자, 정렬).
    combined_largecap_research_v1 = sp500_current ∪ sp500_proxy_candidates_v1 (deterministic sorted union).
    """
    u = universe_name.strip()
    if u == UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1:
        a = set(_latest_symbols_for_universe(client, UNIVERSE_SP500_CURRENT))
        b = set(_latest_symbols_for_universe(client, UNIVERSE_PROXY_CANDIDATES))
        return sorted(a | b)
    if u in (UNIVERSE_SP500_CURRENT, UNIVERSE_PROXY_CANDIDATES):
        return _latest_symbols_for_universe(client, u)
    raise ValueError(
        f"unknown universe slice: {universe_name!r}; "
        f"expected one of {ALL_RESEARCH_SLICES}"
    )
