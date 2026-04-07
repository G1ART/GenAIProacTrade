"""Deterministic substrate coverage metrics per universe (PIT join, quality shares)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from db import records as dbrec
from public_depth.constants import DEFAULT_STATE_CHANGE_SCORES_LIMIT
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import (
    norm_cik,
    norm_signal_date,
    pick_state_change_at_or_before_signal,
    safe_float,
    state_change_rows_by_cik_sorted,
)


def _quality_shares_from_runs(runs: list[dict[str, Any]]) -> dict[str, float | None]:
    if not runs:
        return {
            "thin_input_share": None,
            "degraded_share": None,
            "strong_share": None,
            "usable_with_gaps_share": None,
        }
    c: Counter[str] = Counter(str(r.get("quality_class") or "") for r in runs)
    n = len(runs)
    return {
        "thin_input_share": c.get("thin_input", 0) / n,
        "degraded_share": c.get("degraded", 0) / n,
        "strong_share": c.get("strong", 0) / n,
        "usable_with_gaps_share": c.get("usable_with_gaps", 0) / n,
    }


def _dominant_exclusions(exclusion_counter: Counter[str]) -> list[dict[str, Any]]:
    items = [{"reason": k, "count": int(v)} for k, v in exclusion_counter.items() if v > 0]
    items.sort(key=lambda x: (-x["count"], x["reason"]))
    return items


def compute_substrate_coverage(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_scores_limit: int = DEFAULT_STATE_CHANGE_SCORES_LIMIT,
    quality_run_lookback: int = 40,
    symbol_queues_out: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """
    유니버스 멤버십 최신 as_of 기준.
    반환: (metrics_json, exclusion_distribution flat dict for DB jsonb).
    symbol_queues_out 이 주어지면 Phase 18용으로 주요 제외 사유별 심볼 목록을 채운다(정렬된 리스트).
    """
    as_of = dbrec.fetch_max_as_of_universe(client, universe_name=universe_name)
    symbols = (
        dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of
        )
        if as_of
        else []
    )
    exclusion_panel = Counter[str]()
    base: dict[str, Any] = {
        "universe_name": universe_name,
        "as_of_date": as_of,
        "n_issuer_universe": len(symbols),
        "state_change_run_id": None,
        "panel_limit_used": panel_limit,
        "state_change_scores_limit_used": state_change_scores_limit,
    }

    quality_runs = dbrec.fetch_public_core_cycle_quality_runs_for_universe(
        client, universe_name=universe_name, limit=quality_run_lookback
    )
    base.update(_quality_shares_from_runs(quality_runs))

    if not as_of or not symbols:
        base.update(
            {
                "n_issuer_resolved_cik": 0,
                "n_issuer_with_factor_panel": 0,
                "n_issuer_with_validation_panel_symbol": 0,
                "n_issuer_with_next_quarter_excess": 0,
                "n_issuer_with_state_change_cik": 0,
                "validation_panel_row_count": 0,
                "validation_join_row_count": 0,
                "joined_recipe_substrate_row_count": 0,
                "n_issuer_no_validation_panel_row": 0,
                "dominant_exclusion_reasons": [],
            }
        )
        if not symbols:
            exclusion_panel["empty_universe_or_no_as_of"] = 1
        if symbol_queues_out is not None:
            symbol_queues_out.clear()
        return base, dict(exclusion_panel)

    cik_by_symbol = dbrec.fetch_cik_map_for_tickers(client, symbols)
    resolved_ciks = {
        norm_cik(c)
        for c in cik_by_symbol.values()
        if c and str(c).strip() and norm_cik(c)
    }
    base["n_issuer_resolved_cik"] = sum(
        1 for s in symbols if cik_by_symbol.get(s.upper().strip())
    )

    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=list(resolved_ciks), limit=max(panel_limit, 50_000)
    )
    ciks_with_factor = {norm_cik(k[0]) for k in factor_map}
    base["n_issuer_with_factor_panel"] = sum(
        1 for ck in resolved_ciks if ck in ciks_with_factor
    )

    state_run_id = dbrec.fetch_latest_state_change_run_id(
        client, universe_name=universe_name
    )
    base["state_change_run_id"] = state_run_id
    scores: list[dict[str, Any]] = []
    if state_run_id:
        scores = dbrec.fetch_state_change_scores_for_run(
            client, run_id=state_run_id, limit=state_change_scores_limit
        )
    sc_by_cik = state_change_rows_by_cik_sorted(scores)
    universe_ciks_set = resolved_ciks
    base["n_issuer_with_state_change_cik"] = sum(
        1 for ck in universe_ciks_set if ck in sc_by_cik
    )

    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=panel_limit
    )
    base["validation_panel_row_count"] = len(panels)

    symbols_upper = {s.upper().strip() for s in symbols}
    symbols_with_any_panel: set[str] = set()
    validation_join = 0
    joined_substrate = 0
    q_missing_excess: set[str] = set()
    q_no_sc: set[str] = set()

    for p in panels:
        sym = str(p.get("symbol") or "").upper().strip()
        if sym:
            symbols_with_any_panel.add(sym)
        excess = safe_float(p.get(EXCESS_FIELD))
        if excess is None:
            exclusion_panel["missing_excess_return_1q"] += 1
            if sym:
                q_missing_excess.add(sym)
            continue
        validation_join += 1
        cik = norm_cik(p.get("cik"))
        sig = norm_signal_date(p.get("signal_available_date"))
        if not cik or not sig:
            exclusion_panel["missing_cik_or_signal_date"] += 1
            continue
        sc_row = pick_state_change_at_or_before_signal(
            sc_by_cik, cik=cik, signal_date=sig
        )
        if not sc_row:
            exclusion_panel["no_state_change_join"] += 1
            if sym:
                q_no_sc.add(sym)
            continue
        sc_score = safe_float(sc_row.get("state_change_score_v1"))
        if sc_score is None:
            exclusion_panel["missing_state_change_score"] += 1
            continue
        joined_substrate += 1

    symbols_missing_panel = symbols_upper - symbols_with_any_panel
    base["n_issuer_no_validation_panel_row"] = len(symbols_missing_panel)
    if symbols_missing_panel:
        exclusion_panel["no_validation_panel_for_symbol"] += len(symbols_missing_panel)

    base["n_issuer_with_validation_panel_symbol"] = len(symbols_with_any_panel)
    issuers_nq = {
        str(p.get("symbol") or "").upper().strip()
        for p in panels
        if safe_float(p.get(EXCESS_FIELD)) is not None
    }
    base["n_issuer_with_next_quarter_excess"] = len(issuers_nq & symbols_upper)

    base["validation_join_row_count"] = validation_join
    base["joined_recipe_substrate_row_count"] = joined_substrate
    base["dominant_exclusion_reasons"] = _dominant_exclusions(exclusion_panel)

    if symbol_queues_out is not None:
        missing_panel_syms = symbols_upper - symbols_with_any_panel
        symbol_queues_out["no_validation_panel_for_symbol"] = sorted(missing_panel_syms)
        symbol_queues_out["missing_excess_return_1q"] = sorted(q_missing_excess)
        symbol_queues_out["no_state_change_join"] = sorted(q_no_sc)

    return base, dict(exclusion_panel)
