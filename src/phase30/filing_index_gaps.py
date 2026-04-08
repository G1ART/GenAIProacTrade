"""`no_filing_index_for_cik` 타깃 리포트·상한 SEC ingest 수리."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import (
    classify_cik_quarter_snapshot_gap,
    report_quarter_snapshot_backfill_gaps,
)
from research_validation.metrics import norm_cik
from sec.ingest_company_sample import run_sample_ingest


def report_filing_index_gap_targets(
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
        if str(r.get("class") or "") == "no_filing_index_for_cik"
    ]
    seen: set[str] = set()
    unique_targets: list[dict[str, Any]] = []
    for r in rows:
        ck = str(r.get("cik") or "").strip()
        nk = norm_cik(ck) if ck else ""
        key = nk or f"sym:{str(r.get('symbol') or '').upper().strip()}"
        if key in seen:
            continue
        seen.add(key)
        unique_targets.append(r)
    return {
        "ok": True,
        "universe_name": universe_name,
        "source": "phase29_quarter_snapshot_classification",
        "no_filing_index_row_count": len(rows),
        "no_filing_index_unique_cik_count": len(unique_targets),
        "targets": unique_targets,
        "targets_sample": unique_targets[:50],
    }


def _resolve_ticker_for_filing_ingest(
    client: Any, *, symbol: str, cik: str
) -> tuple[str | None, str | None]:
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


def run_filing_index_backfill_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 40,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    rep = report_filing_index_gap_targets(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    targets: list[dict[str, Any]] = list(rep.get("targets") or [])
    filing_index_repaired_now: list[dict[str, Any]] = []
    deferred_external_source_gap: list[dict[str, Any]] = []
    blocked_identity_or_mapping_issue: list[dict[str, Any]] = []

    network_attempts = 0
    for row in targets:
        if network_attempts >= max_cik_repairs:
            deferred_external_source_gap.append(
                {**row, "reason": "deferred_repair_cap"}
            )
            continue
        cik = str(row.get("cik") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        ticker, br = _resolve_ticker_for_filing_ingest(client, symbol=symbol, cik=cik)
        if br:
            blocked_identity_or_mapping_issue.append(
                {"symbol": symbol, "cik": cik, "reason": br}
            )
            continue
        assert ticker is not None
        network_attempts += 1
        try:
            out = run_sample_ingest(ticker, settings, client=client)
        except Exception as ex:  # noqa: BLE001
            deferred_external_source_gap.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "ticker_attempted": ticker,
                    "reason": "external_fetch_or_ingest_failed",
                    "error": str(ex),
                }
            )
            continue
        pipe_cik = str(out.get("cik") or "").strip()
        if cik and norm_cik(pipe_cik) != norm_cik(cik):
            blocked_identity_or_mapping_issue.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "ticker_attempted": ticker,
                    "reason": "ingested_cik_mismatch",
                    "ingested_cik": pipe_cik,
                }
            )
            continue
        fi_ok = bool(out.get("filing_index_inserted") or out.get("filing_index_updated"))
        if not fi_ok:
            deferred_external_source_gap.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "ticker_attempted": ticker,
                    "reason": "filing_index_not_touched",
                    "ingest_summary": out,
                }
            )
            continue
        ck_use = str(cik or pipe_cik).strip()
        cls_after = classify_cik_quarter_snapshot_gap(client, cik=ck_use)
        raw_chk = (
            client.table("raw_xbrl_facts")
            .select("id")
            .eq("cik", ck_use)
            .limit(1)
            .execute()
        )
        raw_xbrl_present_after = bool(raw_chk.data)
        snaps = dbrec.fetch_issuer_quarter_snapshots_for_cik(client, cik=ck_use)
        filing_index_repaired_now.append(
            {
                "symbol": symbol,
                "cik": ck_use,
                "ticker": ticker,
                "ingest_summary": out,
                "quarter_snapshot_class_after_filing_ingest": cls_after,
                "raw_xbrl_present_after": raw_xbrl_present_after,
                "issuer_quarter_snapshot_count_after": len(snaps),
            }
        )

    raw_xbrl_after_filing_ingest_count = sum(
        1 for e in filing_index_repaired_now if e.get("raw_xbrl_present_after")
    )
    downstream_snapshot_after_filing_ingest_count = sum(
        1
        for e in filing_index_repaired_now
        if int(e.get("issuer_quarter_snapshot_count_after") or 0) > 0
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "filing_index_backfill",
        "max_cik_repairs": max_cik_repairs,
        "network_ingest_attempts": network_attempts,
        "filing_index_repaired_now": filing_index_repaired_now,
        "filing_index_repaired_now_count": len(filing_index_repaired_now),
        "raw_xbrl_present_after_filing_ingest_count": raw_xbrl_after_filing_ingest_count,
        "downstream_snapshot_present_after_filing_ingest_count": downstream_snapshot_after_filing_ingest_count,
        "repaired_now_semantics": "filing_index_touch_only_use_split_counts_for_raw_snapshot",
        "repaired_now": filing_index_repaired_now,
        "repaired_now_count": len(filing_index_repaired_now),
        "deferred_external_source_gap_count": len(deferred_external_source_gap),
        "blocked_identity_or_mapping_issue_count": len(blocked_identity_or_mapping_issue),
        "deferred_external_source_gap_sample": deferred_external_source_gap[:40],
        "blocked_identity_or_mapping_issue": blocked_identity_or_mapping_issue[:80],
        "preflight_unique_targets_count": len(targets),
    }


def export_filing_index_gap_targets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    rep = report_filing_index_gap_targets(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    flat: list[dict[str, Any]] = list(rep.get("targets") or [])
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and flat:
        keys = sorted({k for row in flat for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)
    elif fmt == "csv":
        p.write_text("symbol,cik,norm_cik\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "path": str(p), "format": fmt}
