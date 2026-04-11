"""터치 심볼: forward next_quarter vs validation excess_return_1q 전파 갭 감사."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase33.metric_truth_audit import _panel_rows_for_symbols
from phase33.phase32_bundle_io import load_phase32_bundle, phase32_touched_symbols
from phase33.price_coverage import classify_price_gap_for_forward_row
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import norm_cik, safe_float

PROPAGATION_CLASSES = (
    "forward_present_validation_not_refreshed",
    "forward_present_validation_refresh_failed",
    "forward_not_present_window_not_matured",
    "forward_not_present_other_gap",
    "synchronized",
)


def _fetch_forward_map(
    client: Any, *, symbol: str, signal_date_s: str | None
) -> dict[str, dict[str, Any]]:
    if not signal_date_s:
        return {}
    r = (
        client.table("forward_returns_daily_horizons")
        .select("*")
        .eq("symbol", symbol.upper().strip())
        .eq("signal_date", str(signal_date_s)[:10])
        .execute()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in r.data or []:
        ht = str(row.get("horizon_type") or "")
        out[ht] = dict(row)
    return out


def classify_propagation_gap(
    *,
    validation_excess_1q: Any,
    forward_nq_row: dict[str, Any] | None,
    price_classification: str,
    refresh_attempt_failed: bool = False,
    signal_date_present: bool = True,
) -> str:
    """단위 행 분류(테스트·오케스트레이터 공용)."""
    val_ex = safe_float(validation_excess_1q)
    fwd_ex = (
        safe_float(forward_nq_row.get("excess_forward_return"))
        if forward_nq_row
        else None
    )
    if not signal_date_present:
        return "forward_not_present_other_gap"

    if fwd_ex is not None:
        if val_ex is None:
            if refresh_attempt_failed:
                return "forward_present_validation_refresh_failed"
            return "forward_present_validation_not_refreshed"
        return "synchronized"

    if price_classification == "lookahead_window_not_matured":
        return "forward_not_present_window_not_matured"
    return "forward_not_present_other_gap"


def report_forward_validation_propagation_gaps(
    client: Any,
    *,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    refresh_failed_keys: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("phase32_bundle or phase32_bundle_path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)

    touched = phase32_touched_symbols(phase32_bundle)
    panels = _panel_rows_for_symbols(client, symbols=touched, panel_limit=panel_limit)
    rf_keys = refresh_failed_keys or set()

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {k: 0 for k in PROPAGATION_CLASSES}
    forward_row_present_count = 0

    for p in panels:
        sym = str(p.get("symbol") or "").upper().strip()
        sig = p.get("signal_available_date")
        sig_s = str(sig)[:10] if sig is not None else ""
        cik = norm_cik(p.get("cik"))
        acc = str(p.get("accession_no") or "")
        fv = str(p.get("factor_version") or "")
        fwd = _fetch_forward_map(client, symbol=sym, signal_date_s=sig_s or None)
        nq = fwd.get("next_quarter")
        if nq is not None and safe_float(nq.get("excess_forward_return")) is not None:
            forward_row_present_count += 1

        price_c = (
            classify_price_gap_for_forward_row(
                client,
                symbol=sym,
                signal_date_s=sig_s or "1970-01-01",
                price_lookahead_days=price_lookahead_days,
            )
            if sig_s
            else {"classification": "symbol_registry_or_time_alignment_issue", "detail": "no_signal_date"}
        )
        pc = str(price_c.get("classification") or "symbol_registry_or_time_alignment_issue")
        rfk = (cik, acc, fv)
        cls = classify_propagation_gap(
            validation_excess_1q=p.get(EXCESS_FIELD),
            forward_nq_row=nq,
            price_classification=pc,
            refresh_attempt_failed=bool(rfk in rf_keys),
            signal_date_present=bool(sig_s),
        )
        counts[cls] = counts.get(cls, 0) + 1
        rows.append(
            {
                "symbol": sym,
                "cik": cik,
                "accession_no": acc,
                "factor_version": fv,
                "signal_available_date": sig_s or None,
                "validation_excess_return_1q": p.get(EXCESS_FIELD),
                "forward_next_quarter_excess": (
                    nq.get("excess_forward_return") if nq else None
                ),
                "price_gap": price_c,
                "classification": cls,
            }
        )

    gap_rows = [r for r in rows if r["classification"] != "synchronized"]

    return {
        "ok": True,
        "phase32_touched_symbol_count": len(touched),
        "validation_panel_rows_scanned": len(panels),
        "forward_row_present_count": forward_row_present_count,
        "classification_counts": {k: counts[k] for k in PROPAGATION_CLASSES},
        "gap_row_count": len(gap_rows),
        "rows": rows,
    }


def export_forward_validation_propagation_gaps(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())
