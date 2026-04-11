"""Phase 32 NQ insufficient_price_history 중 현재 시점에만 성숙해 계산 가능한 창만 forward 재시도."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db.client import get_supabase_client
from db import records as dbrec
from market.forward_returns_run import run_forward_returns_build_from_rows
from phase33.metric_truth_audit import report_forward_metric_truth_audit
from phase33.phase32_bundle_io import (
    load_phase32_bundle,
    phase32_insufficient_price_errors_next_q,
)
from phase33.price_coverage import classify_price_gap_for_forward_row
from research_validation.metrics import norm_cik

MATURITY_ELIGIBLE_CLASS = "would_compute_now"


def _bucket_non_retry(classification: str) -> str:
    if classification == "lookahead_window_not_matured":
        return "still_lookahead_window_not_matured"
    if classification == "missing_market_prices_daily_window":
        return "missing_market_prices_daily_window"
    return "registry_or_time_alignment_issue"


def report_matured_forward_retry_targets(
    client: Any,
    *,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("bundle or path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)
    errs = phase32_insufficient_price_errors_next_q(phase32_bundle)
    rows: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    counts_skip: dict[str, int] = {}

    for e in errs:
        sym = str(e.get("symbol") or "").upper().strip()
        sig = str(e.get("signal_date") or "")[:10]
        if not sym or not sig:
            continue
        pg = classify_price_gap_for_forward_row(
            client,
            symbol=sym,
            signal_date_s=sig,
            price_lookahead_days=price_lookahead_days,
        )
        cls = str(pg.get("classification") or "")
        if cls == MATURITY_ELIGIBLE_CLASS:
            bucket = "maturity_eligible"
            eligible.append({**e, "price_gap": pg})
        else:
            bucket = _bucket_non_retry(cls)
            counts_skip[bucket] = counts_skip.get(bucket, 0) + 1
        rows.append({**e, "price_gap": pg, "retry_bucket": bucket})

    return {
        "ok": True,
        "source_error_row_count": len(errs),
        "maturity_eligible_count": len(eligible),
        "still_not_matured_count": counts_skip.get(
            "still_lookahead_window_not_matured", 0
        ),
        "missing_market_prices_daily_window_count": counts_skip.get(
            "missing_market_prices_daily_window", 0
        ),
        "registry_or_time_alignment_issue_count": counts_skip.get(
            "registry_or_time_alignment_issue", 0
        ),
        "rows": rows,
        "maturity_eligible_rows": eligible,
    }


def export_matured_forward_retry_targets(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def run_matured_forward_retry(
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
    rep = report_matured_forward_retry_targets(
        client,
        phase32_bundle=phase32_bundle,
        price_lookahead_days=price_lookahead_days,
    )
    eligible = rep.get("maturity_eligible_rows") or []
    syms = sorted(
        {str(r.get("symbol") or "").upper().strip() for r in eligible if r.get("symbol")}
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
            "repair": "matured_forward_retry",
            "skipped": True,
            "reason": "no_maturity_eligible_targets",
            "target_report": rep,
            "forward_build": {"skipped": True},
            "matured_forward_retry_success_count": 0,
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_before,
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
            "repair": "matured_forward_retry",
            "skipped": True,
            "reason": "no_cik_from_validation_panels_for_matured_symbols",
            "target_report": rep,
            "forward_build": {"skipped": True},
            "matured_forward_retry_success_count": 0,
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_before,
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
            "phase34": "matured_forward_retry",
            "n_maturity_eligible_source_rows": len(eligible),
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

    return {
        "ok": True,
        "repair": "matured_forward_retry",
        "target_report": rep,
        "symbols": syms,
        "factor_panels_input": len(panels),
        "forward_build": build_out,
        "matured_forward_retry_success_count": int(
            build_out.get("success_operations") or 0
        ),
        "metric_truth_before": truth_before,
        "metric_truth_after": truth_after,
    }
