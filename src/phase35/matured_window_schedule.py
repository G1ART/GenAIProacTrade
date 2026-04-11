"""Phase 34 미성숙 7행(또는 번들 추출) — 성숙 여부·스케줄·선택적 forward 재시도."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db.client import get_supabase_client
from db import records as dbrec
from market.forward_returns_run import TRADING_DAYS_1Q, run_forward_returns_build_from_rows
from phase33.price_coverage import classify_price_gap_for_forward_row
from phase35.phase34_bundle_io import (
    immature_gap_rows_from_phase34,
    load_phase34_bundle,
)
from research_validation.metrics import norm_cik, norm_signal_date


def report_matured_window_schedule_for_forward(
    client: Any,
    *,
    phase34_bundle: dict[str, Any] | None = None,
    phase34_bundle_path: str | None = None,
    price_lookahead_days: int = 400,
    expected_symbols: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if phase34_bundle is None:
        if not phase34_bundle_path:
            raise ValueError("bundle or path required")
        phase34_bundle = load_phase34_bundle(phase34_bundle_path)
    rows = immature_gap_rows_from_phase34(phase34_bundle)
    sym_set = {str(r.get("symbol") or "").upper().strip() for r in rows}
    exp = {s.upper().strip() for s in (expected_symbols or ())}
    isolation_ok = not exp or exp <= sym_set

    out_rows: list[dict[str, Any]] = []
    mature_now: list[dict[str, Any]] = []
    still_immature: list[dict[str, Any]] = []

    for ref in rows:
        sym = str(ref.get("symbol") or "").upper().strip()
        sig_s = str(ref.get("signal_available_date") or "")[:10]
        if not sym or len(sig_s) < 10:
            continue
        pg = classify_price_gap_for_forward_row(
            client,
            symbol=sym,
            signal_date_s=sig_s,
            price_lookahead_days=price_lookahead_days,
        )
        cls = str(pg.get("classification") or "")
        n_after = pg.get("sessions_on_or_after_signal")
        shortfall = None
        if isinstance(n_after, int):
            shortfall = max(0, TRADING_DAYS_1Q + 1 - n_after)
        est_days = None
        if shortfall is not None and shortfall > 0:
            est_days = int(shortfall * (365 / 252) + 1)

        row_out = {
            "symbol": sym,
            "signal_available_date": sig_s,
            "price_gap": pg,
            "sessions_shortfall_vs_nq": shortfall,
            "approx_trading_sessions_still_needed": shortfall,
            "calendar_day_hint_for_checkpoint": est_days,
            "schedule_note": (
                "re-run classify_price_gap_for_forward_row; retry forward when "
                "classification is would_compute_now"
            ),
        }
        if cls == "would_compute_now":
            row_out["eligible_for_forward_retry_now"] = True
            mature_now.append(row_out)
        else:
            row_out["eligible_for_forward_retry_now"] = False
            still_immature.append(row_out)
        out_rows.append(row_out)

    return {
        "ok": True,
        "immature_row_count_from_phase34_bundle": len(rows),
        "expected_symbol_isolation_ok": isolation_ok,
        "expected_symbols": sorted(exp) if exp else [],
        "matured_eligible_now_count": len(mature_now),
        "still_not_matured_count": len(still_immature),
        "rows": out_rows,
        "mature_now_rows": mature_now,
    }


def export_matured_window_schedule_for_forward(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def run_matured_window_forward_retry_for_phase34_immature(
    settings: Any,
    *,
    phase34_bundle: dict[str, Any] | None = None,
    phase34_bundle_path: str | None = None,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    rep = report_matured_window_schedule_for_forward(
        client,
        phase34_bundle=phase34_bundle,
        phase34_bundle_path=phase34_bundle_path,
        price_lookahead_days=price_lookahead_days,
    )
    mature = rep.get("mature_now_rows") or []
    syms = sorted({str(r.get("symbol") or "").upper().strip() for r in mature if r.get("symbol")})
    if not syms:
        return {
            "ok": True,
            "repair": "matured_window_forward_retry",
            "skipped": True,
            "reason": "no_immature_rows_became_would_compute_now",
            "schedule_report": rep,
            "forward_build": {"skipped": True},
        }

    val_panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=syms, limit=8000
    )
    cik_to_sym: dict[str, str] = {}
    for p in val_panels:
        ck = norm_cik(p.get("cik"))
        s = str(p.get("symbol") or "").upper().strip()
        if ck and s:
            cik_to_sym[ck] = s
    wanted_ciks = {ck for ck, s in cik_to_sym.items() if s in set(syms)}
    fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=sorted(wanted_ciks), limit=50_000
    )
    fmap_n = {(norm_cik(a), str(b), str(c)): v for (a, b, c), v in fmap.items()}
    panels: list[dict[str, Any]] = []
    for r in mature:
        sym = str(r.get("symbol") or "").upper().strip()
        sig = str(r.get("signal_available_date") or "")[:10]
        for vp in val_panels:
            if str(vp.get("symbol") or "").upper().strip() != sym:
                continue
            if norm_signal_date(vp.get("signal_available_date")) != sig:
                continue
            k = (
                norm_cik(vp.get("cik")),
                str(vp.get("accession_no") or ""),
                str(vp.get("factor_version") or ""),
            )
            prow = fmap_n.get(k)
            if prow:
                panels.append(prow)
            break

    build_out = run_forward_returns_build_from_rows(
        settings,
        panels=panels,
        metadata_json={
            "phase35": "matured_window_forward_retry_for_phase34_immature",
            "n_mature_now_rows": len(mature),
            "n_factor_panels": len(panels),
        },
        price_lookahead_days=price_lookahead_days,
    )

    return {
        "ok": True,
        "repair": "matured_window_forward_retry",
        "schedule_report": rep,
        "symbols_retried": syms,
        "factor_panels_input": len(panels),
        "forward_build": build_out,
        "matured_forward_retry_success_count": int(
            build_out.get("success_operations") or 0
        ),
    }
