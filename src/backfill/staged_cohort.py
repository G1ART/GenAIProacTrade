"""Deterministic staged coverage cohort (30 → 150 → 300+). 무작위 샘플링 없음."""

from __future__ import annotations

from typing import Any, Optional

from backfill.normalize import normalize_ticker_list
from research.universe_slices import (
    UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1,
    UNIVERSE_SP500_CURRENT,
    resolve_slice_symbols,
)

COVERAGE_STAGES = frozenset({"stage_a", "stage_b", "full"})

# stage별 기본 issuer 상한 (issuer_target 미지정 시)
DEFAULT_ISSUER_TARGET_BY_STAGE: dict[str, int] = {
    "stage_a": 150,
    "stage_b": 300,
}


def resolve_issuer_target(
    coverage_stage: str, issuer_target: Optional[int]
) -> Optional[int]:
    """
    full + issuer_target None → 전체 유니버스(상한 없음).
    stage_a / stage_b → 기본 150 / 300.
    """
    if issuer_target is not None:
        return max(1, issuer_target)
    if coverage_stage == "full":
        return None
    d = DEFAULT_ISSUER_TARGET_BY_STAGE.get(coverage_stage)
    if d is None:
        raise ValueError(f"unknown coverage_stage: {coverage_stage!r}")
    return d


def resolve_staged_coverage_tickers(
    client: Any,
    *,
    universe_name: str,
    coverage_stage: str,
    issuer_target: Optional[int] = None,
) -> tuple[list[str], dict[str, Any]]:
    """
    sp500_current 우선, 멤버가 target 미만이면 combined_largecap_research_v1 로 보강(정렬된 합집합).
    티커는 항상 대문자·정렬된 순서로 앞에서부터 N개.
    """
    if coverage_stage not in COVERAGE_STAGES:
        raise ValueError(
            f"unknown coverage_stage {coverage_stage!r}; expected one of {sorted(COVERAGE_STAGES)}"
        )
    target = resolve_issuer_target(coverage_stage, issuer_target)
    u = universe_name.strip()
    primary = list(resolve_slice_symbols(client, u))
    meta: dict[str, Any] = {
        "coverage_stage": coverage_stage,
        "universe_name": u,
        "requested_issuer_target": target,
        "universe_symbol_count_primary": len(primary),
        "cohort_source": "primary_universe_only",
        "fallback_used": False,
    }

    cohort: list[str] = sorted(primary)

    if u == UNIVERSE_SP500_CURRENT and target is not None and len(cohort) < target:
        combined_syms = set(resolve_slice_symbols(client, UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1))
        have = set(cohort)
        extra = sorted(combined_syms - have)
        cohort = cohort + extra
        meta["fallback_used"] = True
        meta["cohort_source"] = (
            "sp500_current_then_combined_largecap_research_v1_extras_sorted"
        )
        meta["universe_symbol_count_after_fallback"] = len(cohort)

    if target is None:
        tickers = normalize_ticker_list(cohort)
    else:
        tickers = normalize_ticker_list(cohort[: min(target, len(cohort))])

    meta["resolved_symbol_count"] = len(tickers)
    meta["resolution_note"] = (
        f"staged {coverage_stage}: deterministic sorted cohort[:{target or 'all'}]"
    )
    return tickers, meta
