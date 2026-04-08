"""`empty_cik` 분류: 멤버십·레지스트리·issuer 매핑 (v1은 자동 변경 없음)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import report_quarter_snapshot_backfill_gaps
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.metrics import norm_cik


def _registry_cik_raw(reg: dict[str, Any] | None) -> str | None:
    if not reg:
        return None
    c = reg.get("cik")
    if c is None or not str(c).strip():
        return None
    return str(c).strip()


def report_empty_cik_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qrep = report_quarter_snapshot_backfill_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    rows = [
        dict(r)
        for r in (qrep.get("classification_rows") or [])
        if str(r.get("class") or "") == "empty_cik"
    ]
    metrics, _ = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    as_of = metrics.get("as_of_date")
    as_of_s = str(as_of)[:10] if as_of else ""

    diagnoses: list[dict[str, Any]] = []
    mem_by_sym: dict[str, dict[str, Any]] = {}
    if as_of_s:
        mem_rows = dbrec.fetch_universe_memberships_for_as_of(
            client, universe_name=universe_name, as_of_date=as_of_s
        )
        mem_by_sym = {
            str(x["symbol"]).upper().strip(): x for x in mem_rows if x.get("symbol")
        }

    symbols_u: list[str] = []
    cik_map: dict[str, str] = {}
    if as_of_s:
        symbols_u = dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of_s
        )
        cik_map = dbrec.fetch_cik_map_for_tickers(client, symbols_u)

    for r in rows:
        sym = str(r.get("symbol") or "").upper().strip()
        d: dict[str, Any] = {
            "symbol": sym,
            "cik_on_row": r.get("cik"),
            "norm_cik": r.get("norm_cik"),
        }
        if not sym:
            d["diagnosis"] = "blocked_no_symbol"
            d["detail"] = "symbol_missing_on_classification_row"
            diagnoses.append(d)
            continue
        if not as_of_s:
            d["diagnosis"] = "indeterminate_no_as_of"
            diagnoses.append(d)
            continue

        mem = mem_by_sym.get(sym)
        mem_cik = str(mem.get("cik") or "").strip() if mem else ""
        reg_rows = dbrec.fetch_market_symbol_registry_rows_for_symbols(client, [sym])
        reg = reg_rows.get(sym)
        reg_cik = _registry_cik_raw(reg)
        map_cik = str(cik_map.get(sym) or "").strip()

        if mem is None:
            d["diagnosis"] = "missing_membership_cik"
            d["detail"] = "symbol_not_in_universe_membership_as_of"
        elif not mem_cik:
            d["diagnosis"] = "missing_membership_cik"
            d["detail"] = "membership_row_present_but_cik_empty"
        elif reg is None:
            d["diagnosis"] = "missing_symbol_in_market_symbol_registry"
        elif not reg_cik:
            d["diagnosis"] = "registry_normalization_mismatch"
            d["detail"] = "registry_row_present_but_cik_empty"
        elif norm_cik(mem_cik) != norm_cik(reg_cik):
            d["diagnosis"] = "registry_normalization_mismatch"
            d["membership_cik"] = mem_cik
            d["registry_cik"] = reg_cik
        elif not map_cik:
            d["diagnosis"] = "issuer_mapping_gap"
            d["detail"] = "no_cik_on_issuer_map_for_symbol"
            d["membership_cik"] = mem_cik
            d["registry_cik"] = reg_cik
        elif norm_cik(mem_cik) != norm_cik(map_cik):
            d["diagnosis"] = "issuer_mapping_gap"
            d["detail"] = "issuer_map_cik_mismatch"
            d["membership_cik"] = mem_cik
            d["registry_cik"] = reg_cik
            d["issuer_map_cik"] = map_cik
        else:
            d["diagnosis"] = "indeterminate_empty_cik_despite_sources"
            d["membership_cik"] = mem_cik
            d["registry_cik"] = reg_cik
            d["issuer_map_cik"] = map_cik
        diagnoses.append(d)

    return {
        "ok": True,
        "universe_name": universe_name,
        "as_of_date": as_of_s,
        "empty_cik_row_count": len(rows),
        "diagnoses": diagnoses,
    }


def run_empty_cik_cleanup_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    rep = report_empty_cik_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "empty_cik_cleanup",
        "mutating_repairs_applied": [],
        "deterministic_repairs_applied": [],
        "report": rep,
        "note": "classification_only_no_automatic_mutations_in_v1",
    }
