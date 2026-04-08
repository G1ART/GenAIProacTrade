"""`filing_index_present_no_raw_facts` 세부 분류·리포트."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import report_quarter_snapshot_backfill_gaps
from research_validation.metrics import norm_cik


def _has_raw_sec_filing(client: Any, *, cik: str) -> bool:
    ck = str(cik).strip()
    if not ck:
        return False
    r = (
        client.table("raw_sec_filings")
        .select("id")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def _has_raw_xbrl(client: Any, *, cik: str) -> bool:
    ck = str(cik).strip()
    if not ck:
        return False
    r = (
        client.table("raw_xbrl_facts")
        .select("id")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def _has_filing_index(client: Any, *, cik: str) -> bool:
    ck = str(cik).strip()
    if not ck:
        return False
    r = (
        client.table("filing_index")
        .select("id")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def classify_raw_facts_gap_detail(
    client: Any, *, cik: str, symbol: str = ""
) -> dict[str, Any]:
    """
    `filing_index_present_no_raw_facts` 타깃에 대한 부가 분류.
    """
    ck = str(cik).strip()
    fi = _has_filing_index(client, cik=ck)
    rx = _has_raw_xbrl(client, cik=ck)
    rs = _has_raw_sec_filing(client, cik=ck)
    if rx:
        return {
            "cik": ck,
            "symbol": str(symbol or "").upper().strip(),
            "sub_reason": "raw_xbrl_present_classifier_stale_or_mismatch",
            "has_filing_index": fi,
            "has_raw_xbrl_facts": True,
            "has_raw_sec_filings": rs,
        }
    if not fi:
        return {
            "cik": ck,
            "symbol": str(symbol or "").upper().strip(),
            "sub_reason": "no_filing_index_inconsistent_with_bucket",
            "has_filing_index": False,
            "has_raw_xbrl_facts": False,
            "has_raw_sec_filings": rs,
        }
    if rs:
        return {
            "cik": ck,
            "symbol": str(symbol or "").upper().strip(),
            "sub_reason": "raw_sec_pipeline_present_xbrl_facts_not_attempted",
            "has_filing_index": True,
            "has_raw_xbrl_facts": False,
            "has_raw_sec_filings": True,
        }
    return {
        "cik": ck,
        "symbol": str(symbol or "").upper().strip(),
        "sub_reason": "no_xbrl_facts_no_sec_raw_row_filing_index_only_or_external_gap",
        "has_filing_index": True,
        "has_raw_xbrl_facts": False,
        "has_raw_sec_filings": False,
    }


def report_raw_facts_gap_targets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
    extra_ciks: list[str] | None = None,
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
        if str(r.get("class") or "") == "filing_index_present_no_raw_facts"
    ]
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in rows:
        ck = str(r.get("cik") or "").strip()
        nk = norm_cik(ck) if ck else ""
        if nk in seen:
            continue
        seen.add(nk)
        unique.append(r)

    for raw in extra_ciks or []:
        ck = str(raw or "").strip()
        nk = norm_cik(ck) if ck else ""
        if not nk or nk in seen:
            continue
        seen.add(nk)
        unique.append({"symbol": "", "cik": ck, "norm_cik": nk, "class": "extra_cik"})

    details: list[dict[str, Any]] = []
    sub_counts: dict[str, int] = {}
    for r in unique:
        d = classify_raw_facts_gap_detail(
            client,
            cik=str(r.get("cik") or ""),
            symbol=str(r.get("symbol") or ""),
        )
        details.append({**r, "gap_detail": d})
        sr = str(d.get("sub_reason") or "unknown")
        sub_counts[sr] = sub_counts.get(sr, 0) + 1

    return {
        "ok": True,
        "universe_name": universe_name,
        "source": "phase29_quarter_snapshot_classification",
        "filing_index_present_no_raw_facts_row_count": len(rows),
        "unique_cik_count": len(unique),
        "sub_reason_counts": dict(sorted(sub_counts.items())),
        "targets": unique,
        "targets_with_detail_sample": details[:60],
    }


def export_raw_facts_gap_targets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
    extra_ciks: list[str] | None = None,
) -> dict[str, Any]:
    rep = report_raw_facts_gap_targets(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        extra_ciks=extra_ciks,
    )
    flat: list[dict[str, Any]] = []
    for t in rep.get("targets") or []:
        d = classify_raw_facts_gap_detail(
            client, cik=str(t.get("cik") or ""), symbol=str(t.get("symbol") or "")
        )
        flat.append({**t, **{f"detail_{k}": v for k, v in d.items()}})
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and flat:
        keys = sorted({k for row in flat for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)
    elif fmt == "csv":
        p.write_text("symbol,cik,sub_reason\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "path": str(p), "format": fmt}
