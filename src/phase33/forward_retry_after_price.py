"""가격 백필 후 Phase 32 `insufficient_price_history`(next_quarter) 심볼만 forward 재빌드."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from db import records as dbrec
from market.forward_returns_run import run_forward_returns_build_from_rows
from phase33.metric_truth_audit import report_forward_metric_truth_audit
from phase33.phase32_bundle_io import (
    load_phase32_bundle,
    phase32_insufficient_price_errors_next_q,
)
from research_validation.metrics import norm_cik


def run_forward_return_retry_after_price_repair(
    settings: Any,
    *,
    universe_name: str,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("bundle or path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)

    client = get_supabase_client(settings)
    errs = phase32_insufficient_price_errors_next_q(phase32_bundle)
    syms = sorted(
        {str(e.get("symbol") or "").upper().strip() for e in errs if e.get("symbol")}
    )
    truth_before = report_forward_metric_truth_audit(
        client,
        universe_name=universe_name,
        phase32_bundle=phase32_bundle,
        panel_limit=panel_limit,
    )

    if not syms:
        return {
            "ok": True,
            "repair": "forward_return_retry_after_price_repair",
            "skipped": True,
            "reason": "no_next_quarter_insufficient_price_errors_in_phase32_bundle",
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_before,
            "forward_build": {"skipped": True},
        }

    val_panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=syms, limit=panel_limit
    )
    cik_to_sym: dict[str, str] = {}
    for p in val_panels:
        ck = norm_cik(p.get("cik"))
        s = str(p.get("symbol") or "").upper().strip()
        if ck and s:
            cik_to_sym[ck] = s
    wanted_ciks = {ck for ck, s in cik_to_sym.items() if s in set(syms)}
    if not wanted_ciks:
        return {
            "ok": True,
            "repair": "forward_return_retry_after_price_repair",
            "skipped": True,
            "reason": "no_cik_from_validation_panels_for_error_symbols",
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_before,
            "forward_build": {"skipped": True},
        }

    fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=sorted(wanted_ciks), limit=max(50_000, panel_limit)
    )
    panels = [
        prow
        for prow in fmap.values()
        if cik_to_sym.get(norm_cik(prow.get("cik")), "") in set(syms)
    ]

    build_out = run_forward_returns_build_from_rows(
        settings,
        panels=panels,
        metadata_json={
            "phase33": "forward_return_retry_after_price_repair",
            "n_symbols_from_phase32_errors": len(syms),
            "n_factor_panels": len(panels),
        },
        price_lookahead_days=price_lookahead_days,
    )

    truth_after = report_forward_metric_truth_audit(
        client,
        universe_name=universe_name,
        phase32_bundle=phase32_bundle,
        panel_limit=panel_limit,
    )

    jb = truth_before.get("joined_recipe_substrate_row_count_live")
    ja = truth_after.get("joined_recipe_substrate_row_count_live")
    joined_delta = None
    if isinstance(jb, int) and isinstance(ja, int):
        joined_delta = ja - jb

    sb = truth_before.get("symbol_cleared_from_missing_excess_queue_count")
    sa = truth_after.get("symbol_cleared_from_missing_excess_queue_count")
    sym_clear_delta = None
    if isinstance(sb, int) and isinstance(sa, int):
        sym_clear_delta = sa - sb

    return {
        "ok": True,
        "repair": "forward_return_retry_after_price_repair",
        "symbols_from_phase32_errors": syms,
        "factor_panels_input": len(panels),
        "forward_build": build_out,
        "metric_truth_before": truth_before,
        "metric_truth_after": truth_after,
        "joined_recipe_unlocked_delta_after_retry": joined_delta,
        "symbol_queue_cleared_delta_after_retry": sym_clear_delta,
    }
