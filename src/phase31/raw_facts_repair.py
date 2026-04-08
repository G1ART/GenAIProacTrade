"""`raw_xbrl_facts` 상한 적재 — `run_facts_extract_for_ticker` 경로."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import classify_cik_quarter_snapshot_gap
from phase31.raw_facts_gaps import report_raw_facts_gap_targets
from research_validation.metrics import norm_cik
from sec.facts.facts_pipeline import run_facts_extract_for_ticker


def _resolve_ticker(client: Any, *, symbol: str, cik: str) -> tuple[str | None, str | None]:
    sym = str(symbol or "").upper().strip()
    if sym:
        return sym, None
    ck = str(cik or "").strip()
    if not ck:
        return None, "empty_symbol_and_cik"
    t = dbrec.fetch_ticker_for_cik(client, cik=ck)
    if t:
        return str(t).upper().strip(), None
    return None, "no_ticker_in_issuer_master_for_cik"


def run_raw_facts_backfill_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 45,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
    extra_ciks: list[str] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    pre = report_raw_facts_gap_targets(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
        extra_ciks=extra_ciks,
    )
    targets = list(pre.get("targets") or [])
    repaired_to_raw_present: list[dict[str, Any]] = []
    deferred_external_source_gap: list[dict[str, Any]] = []
    blocked_mapping_or_schema_seam: list[dict[str, Any]] = []

    attempts = 0
    seen_cik: set[str] = set()
    for row in targets:
        cik = str(row.get("cik") or "").strip()
        if not cik:
            continue
        nk = norm_cik(cik)
        if nk in seen_cik:
            continue
        seen_cik.add(nk)
        cls_before = classify_cik_quarter_snapshot_gap(client, cik=cik)
        if cls_before != "filing_index_present_no_raw_facts":
            blocked_mapping_or_schema_seam.append(
                {
                    "cik": cik,
                    "symbol": row.get("symbol"),
                    "reason": "classification_not_filing_index_present_no_raw_facts",
                    "class_before": cls_before,
                }
            )
            continue
        if attempts >= max_cik_repairs:
            deferred_external_source_gap.append(
                {"cik": cik, "symbol": row.get("symbol"), "reason": "deferred_repair_cap"}
            )
            continue
        symbol = str(row.get("symbol") or "").strip()
        ticker, br = _resolve_ticker(client, symbol=symbol, cik=cik)
        if br:
            blocked_mapping_or_schema_seam.append(
                {"cik": cik, "symbol": symbol, "reason": br}
            )
            continue
        assert ticker is not None
        attempts += 1
        try:
            ext = run_facts_extract_for_ticker(
                client,
                settings,
                ticker,
                run_validation_hook=True,
            )
        except Exception as ex:  # noqa: BLE001
            deferred_external_source_gap.append(
                {
                    "cik": cik,
                    "ticker": ticker,
                    "reason": "facts_extract_exception",
                    "error": str(ex),
                }
            )
            continue
        if not ext.get("ok"):
            deferred_external_source_gap.append(
                {
                    "cik": cik,
                    "ticker": ticker,
                    "reason": "facts_extract_not_ok",
                    "extract": ext,
                }
            )
            continue
        ext_cik = str(ext.get("cik") or "").strip()
        if norm_cik(ext_cik) != norm_cik(cik):
            blocked_mapping_or_schema_seam.append(
                {
                    "cik": cik,
                    "ticker": ticker,
                    "reason": "ingested_cik_mismatch",
                    "extracted_cik": ext_cik,
                }
            )
            continue
        cls_after = classify_cik_quarter_snapshot_gap(client, cik=cik)
        raw_ins = int(ext.get("raw_inserted") or 0) + int(ext.get("raw_skipped") or 0)
        repaired_to_raw_present.append(
            {
                "cik": cik,
                "symbol": symbol,
                "ticker": ticker,
                "class_before": cls_before,
                "class_after": cls_after,
                "extract_summary": {
                    "raw_inserted": ext.get("raw_inserted"),
                    "raw_skipped": ext.get("raw_skipped"),
                    "silver_inserted": ext.get("silver_inserted"),
                    "accession_no": ext.get("accession_no"),
                },
                "raw_fact_rows_touched": raw_ins,
            }
        )

    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "raw_facts_backfill",
        "max_cik_repairs": max_cik_repairs,
        "facts_extract_attempts": attempts,
        "repaired_to_raw_present_count": len(repaired_to_raw_present),
        "deferred_external_source_gap_count": len(deferred_external_source_gap),
        "blocked_mapping_or_schema_seam_count": len(blocked_mapping_or_schema_seam),
        "repaired_to_raw_present": repaired_to_raw_present,
        "deferred_external_source_gap_sample": deferred_external_source_gap[:50],
        "blocked_mapping_or_schema_seam": blocked_mapping_or_schema_seam[:60],
        "preflight": pre,
    }
