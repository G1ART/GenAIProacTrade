"""issuer_quarter_factor_panels + forward returns + 메타 → factor_market_validation_panels."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from db.client import get_supabase_client
from db.records import (
    fetch_factor_panels_all,
    fetch_quarter_snapshot_by_accession,
    fetch_ticker_for_cik,
    upsert_factor_market_validation_panel,
    ingest_run_create_started,
    ingest_run_finalize,
)
from market.run_types import FACTOR_MARKET_VALIDATION_BUILD
from market.signal_date import signal_available_date_from_snapshot

logger = logging.getLogger(__name__)


def _fetch_forward_map(
    client: Any, *, symbol: str, signal_date: str
) -> dict[str, dict[str, Any]]:
    r = (
        client.table("forward_returns_daily_horizons")
        .select("*")
        .eq("symbol", symbol.upper().strip())
        .eq("signal_date", signal_date)
        .execute()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in r.data or []:
        ht = str(row.get("horizon_type") or "")
        out[ht] = dict(row)
    return out


def _fetch_metadata_row(client: Any, *, symbol: str) -> dict[str, Any] | None:
    q = (
        client.table("market_metadata_latest")
        .select("*")
        .eq("symbol", symbol.upper().strip())
        .limit(1)
        .execute()
    )
    if not q.data:
        return None
    return dict(q.data[0])


def run_validation_panel_build(settings: Any, *, limit_panels: int = 2000) -> dict[str, Any]:
    client = get_supabase_client(settings)
    panels = fetch_factor_panels_all(client, limit=limit_panels)
    run_id = ingest_run_create_started(
        client,
        run_type=FACTOR_MARKET_VALIDATION_BUILD,
        target_count=len(panels),
        metadata_json={"limit_panels": limit_panels},
    )
    ok = 0
    fail = 0
    errors: list[dict[str, Any]] = []
    for panel in panels:
        cik = str(panel["cik"])
        acc = str(panel["accession_no"])
        fv = str(panel["factor_version"])
        sym = fetch_ticker_for_cik(client, cik=cik)
        snap = fetch_quarter_snapshot_by_accession(client, cik=cik, accession_no=acc)
        panel_json: dict[str, Any] = {
            "factor_panel_id": str(panel.get("id")),
            "snapshot_present": snap is not None,
        }
        sig_s: str | None = None
        if snap:
            try:
                sd = signal_available_date_from_snapshot(snap)
                sig_s = sd.isoformat()
            except (ValueError, TypeError) as e:
                panel_json["signal_date_error"] = str(e)
        if not sym:
            panel_json["quality_flags"] = panel_json.get("quality_flags", []) + ["missing_ticker"]
        fm = _fetch_metadata_row(client, symbol=sym) if sym else None
        fwd = _fetch_forward_map(client, symbol=sym, signal_date=sig_s) if (sym and sig_s) else {}
        m1 = fwd.get("next_month") or {}
        m1q = fwd.get("next_quarter") or {}
        if not m1:
            panel_json.setdefault("quality_flags", []).append("missing_forward_return_1m")
        if not m1q:
            panel_json.setdefault("quality_flags", []).append("missing_forward_return_1q")
        if not fm:
            panel_json.setdefault("quality_flags", []).append("missing_market_metadata")
        liquidity = {}
        if fm:
            liquidity = {
                "avg_daily_volume": fm.get("avg_daily_volume"),
                "as_of_date": fm.get("as_of_date"),
            }
        try:
            upsert_factor_market_validation_panel(
                client,
                {
                    "cik": cik,
                    "symbol": sym,
                    "accession_no": acc,
                    "fiscal_year": int(panel["fiscal_year"]),
                    "fiscal_period": str(panel["fiscal_period"]),
                    "factor_version": fv,
                    "signal_available_date": sig_s,
                    "market_cap_asof": fm.get("market_cap") if fm else None,
                    "liquidity_proxy_json": liquidity,
                    "raw_return_1m": m1.get("raw_forward_return"),
                    "excess_return_1m": m1.get("excess_forward_return"),
                    "raw_return_1q": m1q.get("raw_forward_return"),
                    "excess_return_1q": m1q.get("excess_forward_return"),
                    "panel_json": panel_json,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            ok += 1
        except Exception as ex:  # noqa: BLE001
            logger.exception("validation panel upsert")
            fail += 1
            errors.append({"cik": cik, "accession_no": acc, "error": str(ex)})
    ingest_run_finalize(
        client,
        run_id=run_id,
        status="completed",
        success_count=ok,
        failure_count=fail,
        error_json={"errors": errors[:100]} if errors else None,
    )
    return {
        "status": "completed",
        "rows_upserted": ok,
        "failures": fail,
        "error_sample": errors[:10],
    }
