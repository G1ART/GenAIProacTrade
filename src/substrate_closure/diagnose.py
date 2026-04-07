"""Gap diagnosis for validation panel, forward return, and state-change join (Phase 25)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from db import records as dbrec
from public_depth.constants import DEFAULT_STATE_CHANGE_SCORES_LIMIT
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import (
    norm_cik,
    norm_signal_date,
    pick_state_change_at_or_before_signal,
    safe_float,
    state_change_rows_by_cik_sorted,
)


def _fetch_validation_rows_for_ciks(
    client: Any, *, ciks: list[str], limit: int = 20_000
) -> list[dict[str, Any]]:
    if not ciks:
        return []
    uniq = sorted({norm_cik(c) for c in ciks if c and str(c).strip()})
    out: list[dict[str, Any]] = []
    chunk_size = 40
    for i in range(0, len(uniq), chunk_size):
        chunk = uniq[i : i + chunk_size]
        r = (
            client.table("factor_market_validation_panels")
            .select("cik,symbol,accession_no,factor_version")
            .in_("cik", chunk)
            .limit(max(1, limit - len(out)))
            .execute()
        )
        out.extend(r.data or [])
        if len(out) >= limit:
            break
    return out[:limit]


def report_validation_panel_coverage_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    """
    no_validation_panel_for_symbol 원인 버킷:
    레지스트리(CIK) 부재, 팩터 패널 부재, 유니버스/정규 티커 불일치, 검증 패널 빌드 누락.
    """
    queues: dict[str, list[str]] = {}
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    missing = list(queues.get("no_validation_panel_for_symbol", []))
    as_of = metrics.get("as_of_date")
    symbols = (
        dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of
        )
        if as_of
        else []
    )
    cik_by_symbol = dbrec.fetch_cik_map_for_tickers(client, symbols)
    resolved_ciks = {
        norm_cik(c)
        for c in cik_by_symbol.values()
        if c and str(c).strip() and norm_cik(c)
    }
    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=list(resolved_ciks), limit=max(panel_limit, 50_000)
    )
    ciks_with_factor = {norm_cik(k[0]) for k in factor_map}

    val_by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _fetch_validation_rows_for_ciks(
        client, ciks=list(resolved_ciks), limit=50_000
    ):
        ck = norm_cik(row.get("cik"))
        if ck:
            val_by_cik[ck].append(dict(row))

    buckets: dict[str, list[str]] = defaultdict(list)
    for sym in missing:
        su = sym.upper().strip()
        raw_cik = cik_by_symbol.get(su)
        if not raw_cik or not str(raw_cik).strip():
            buckets["no_cik_registry_for_symbol"].append(sym)
            continue
        nc = norm_cik(raw_cik)
        if nc not in ciks_with_factor:
            buckets["no_issuer_quarter_factor_panel_for_cik"].append(sym)
            continue
        canonical = dbrec.fetch_ticker_for_cik(client, cik=str(raw_cik))
        cu = (canonical or "").upper().strip()
        rows = val_by_cik.get(nc, [])
        syms_on_rows = {str(r.get("symbol") or "").upper().strip() for r in rows}
        if su in syms_on_rows:
            buckets["data_inconsistency_panel_marked_missing_but_row_exists"].append(sym)
            continue
        if rows and cu and cu != su and cu in syms_on_rows:
            buckets["universe_symbol_vs_canonical_ticker_mismatch"].append(sym)
            continue
        if not rows:
            buckets["validation_panel_build_omission_for_cik"].append(sym)
        else:
            buckets["validation_row_symbol_mismatch_other"].append(sym)

    return {
        "ok": True,
        "universe_name": universe_name,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "missing_symbol_count": len(missing),
        "missing_symbols_sample": sorted(missing)[:80],
        "reason_buckets": {k: sorted(set(v)) for k, v in buckets.items()},
        "reason_bucket_counts": {k: len(set(v)) for k, v in buckets.items()},
    }


def report_forward_return_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    """missing_excess_return_1q 행 단위 원인: 시그널일, forward 부재, excess 공백, 기타."""
    queues: dict[str, list[str]] = {}
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    syms = queues.get("missing_excess_return_1q", [])
    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=syms, limit=panel_limit
    )

    row_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in panels:
        if safe_float(p.get(EXCESS_FIELD)) is not None:
            continue
        sym = str(p.get("symbol") or "").upper().strip()
        sig = norm_signal_date(p.get("signal_available_date"))
        acc = str(p.get("accession_no") or "")
        cik = norm_cik(p.get("cik"))
        if not sig:
            row_buckets["missing_signal_date_on_panel"].append(
                {"symbol": sym, "cik": cik, "accession_no": acc}
            )
            continue
        fr = dbrec.fetch_forward_return_for_signal(
            client,
            symbol=sym,
            signal_date=sig,
            horizon_type="next_quarter",
        )
        if not fr:
            row_buckets["no_forward_row_next_quarter"].append(
                {"symbol": sym, "signal_date": sig, "cik": cik, "accession_no": acc}
            )
        elif fr.get("raw_forward_return") is None:
            row_buckets["forward_row_missing_raw_return"].append(
                {"symbol": sym, "signal_date": sig}
            )
        elif fr.get("excess_forward_return") is None:
            row_buckets["excess_null_despite_forward_row"].append(
                {"symbol": sym, "signal_date": sig}
            )
        else:
            row_buckets["panel_stale_or_validation_refresh_needed"].append(
                {"symbol": sym, "signal_date": sig}
            )

    return {
        "ok": True,
        "universe_name": universe_name,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "rows_missing_excess": sum(len(v) for v in row_buckets.values()),
        "row_reason_buckets": {k: v[:200] for k, v in row_buckets.items()},
        "row_reason_counts": {k: len(v) for k, v in row_buckets.items()},
    }


def report_state_change_join_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_scores_limit: int = DEFAULT_STATE_CHANGE_SCORES_LIMIT,
) -> dict[str, Any]:
    """no_state_change_join: CIK 미적재, PIT 이전 as_of 부재, 점수 필드 공백 등."""
    queues: dict[str, list[str]] = {}
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
        symbol_queues_out=queues,
    )
    syms = set(queues.get("no_state_change_join", []))
    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=sorted(syms), limit=panel_limit
    )

    state_run_id = metrics.get("state_change_run_id")
    scores: list[dict[str, Any]] = []
    if state_run_id:
        scores = dbrec.fetch_state_change_scores_for_run(
            client, run_id=str(state_run_id), limit=state_change_scores_limit
        )
    sc_by_cik = state_change_rows_by_cik_sorted(scores)

    row_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in panels:
        if safe_float(p.get(EXCESS_FIELD)) is None:
            continue
        sym = str(p.get("symbol") or "").upper().strip()
        if sym not in syms:
            continue
        cik = norm_cik(p.get("cik"))
        sig = norm_signal_date(p.get("signal_available_date"))
        if not cik or not sig:
            row_buckets["missing_cik_or_signal_for_join"].append(
                {"symbol": sym, "cik": cik, "signal_date": sig}
            )
            continue
        sc_row = pick_state_change_at_or_before_signal(
            sc_by_cik, cik=cik, signal_date=sig
        )
        if sc_row and safe_float(sc_row.get("state_change_score_v1")) is not None:
            continue
        if cik not in sc_by_cik:
            row_buckets["no_state_change_scores_for_cik_in_latest_run"].append(
                {"symbol": sym, "cik": cik, "signal_date": sig}
            )
            continue
        pairs = sc_by_cik[cik]
        dates = [x[0] for x in pairs]
        if not dates or min(dates) > sig:
            row_buckets["all_state_change_as_of_after_signal_pit_gap"].append(
                {
                    "symbol": sym,
                    "cik": cik,
                    "signal_date": sig,
                    "earliest_sc": dates[0] if dates else None,
                }
            )
            continue
        sc_row2 = pick_state_change_at_or_before_signal(
            sc_by_cik, cik=cik, signal_date=sig
        )
        if not sc_row2:
            row_buckets["pick_state_change_returned_none"].append(
                {"symbol": sym, "cik": cik, "signal_date": sig}
            )
            continue
        if safe_float(sc_row2.get("state_change_score_v1")) is None:
            row_buckets["state_change_row_missing_score_v1"].append(
                {"symbol": sym, "cik": cik, "signal_date": sig}
            )

    return {
        "ok": True,
        "universe_name": universe_name,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "state_change_run_id": state_run_id,
        "row_reason_buckets": {k: v[:200] for k, v in row_buckets.items()},
        "row_reason_counts": {k: len(v) for k, v in row_buckets.items()},
    }


def collect_panels_for_validation_repair(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """validation_panel_build_omission_for_cik 대상 CIK의 issuer_quarter_factor_panels 행."""
    rep = report_validation_panel_coverage_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    syms = rep["reason_buckets"].get("validation_panel_build_omission_for_cik", [])
    as_of = rep["metrics"].get("as_of_date")
    symbols = (
        dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of
        )
        if as_of
        else []
    )
    cik_by_symbol = dbrec.fetch_cik_map_for_tickers(client, symbols)
    ciks: set[str] = set()
    for s in syms:
        raw = cik_by_symbol.get(s.upper().strip())
        if raw:
            ciks.add(norm_cik(raw))

    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=list(ciks), limit=max(panel_limit, 50_000)
    )
    panels = list(factor_map.values())
    meta = {
        "universe_name": universe_name,
        "target_cik_count": len(ciks),
        "panel_rows": len(panels),
        "diagnosis_summary": rep["reason_bucket_counts"],
    }
    return panels, meta


def collect_panels_for_forward_repair(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """no_forward_row_next_quarter 등 백필 후보 issuer_quarter 행."""
    rep = report_forward_return_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    keys = rep["row_reason_buckets"].get("no_forward_row_next_quarter", [])
    cik_acc: set[tuple[str, str]] = set()
    for row in keys:
        ck = norm_cik(row.get("cik"))
        acc = str(row.get("accession_no") or "")
        if ck and acc:
            cik_acc.add((ck, acc))

    if not cik_acc:
        return [], {
            "universe_name": universe_name,
            "panel_rows": 0,
            "distinct_cik_accession": 0,
            "forward_gap_counts": rep["row_reason_counts"],
        }

    ciks = sorted({a[0] for a in cik_acc})
    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=ciks, limit=max(panel_limit, 50_000)
    )
    panels: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for key, prow in factor_map.items():
        ck = norm_cik(key[0])
        acc = str(key[1])
        if (ck, acc) in cik_acc and key not in seen:
            seen.add(key)
            panels.append(prow)

    meta = {
        "universe_name": universe_name,
        "distinct_cik_accession": len(cik_acc),
        "panel_rows": len(panels),
        "forward_gap_counts": rep["row_reason_counts"],
    }
    return panels, meta
