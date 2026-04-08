"""`missing_quarter_snapshot_for_cik` 분류 + silver→스냅샷 재구성(상한)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from phase28.factor_materialization import report_factor_panel_materialization_gaps
from sec.facts.facts_pipeline import rebuild_quarter_snapshot_from_db


def classify_cik_quarter_snapshot_gap(client: Any, *, cik: str) -> str:
    """단일 CIK에 대한 결정적 분류(첫 매칭 증거 기준)."""
    ck = str(cik).strip()
    if not ck:
        return "empty_cik"
    snaps = dbrec.fetch_issuer_quarter_snapshots_for_cik(client, cik=ck)
    if snaps:
        return "unexpected_snapshots_present"
    fi = (
        client.table("filing_index")
        .select("id")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    if not fi.data:
        return "no_filing_index_for_cik"
    raw = (
        client.table("raw_xbrl_facts")
        .select("accession_no")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    if not raw.data:
        return "filing_index_present_no_raw_facts"
    silv = (
        client.table("silver_xbrl_facts")
        .select("accession_no")
        .eq("cik", ck)
        .limit(1)
        .execute()
    )
    if not silv.data:
        return "raw_present_no_silver_facts"
    acc = str(silv.data[0].get("accession_no") or "")
    if not acc:
        return "silver_row_missing_accession"
    ex = (
        client.table("issuer_quarter_snapshots")
        .select("id")
        .eq("cik", ck)
        .eq("accession_no", acc)
        .limit(1)
        .execute()
    )
    if ex.data:
        return "snapshot_exists_for_sample_accession_other_gap"
    return "silver_present_snapshot_materialization_missing"


def find_silver_accession_without_snapshot(
    client: Any, *, cik: str, scan_limit: int = 400
) -> str | None:
    ck = str(cik).strip()
    r = (
        client.table("silver_xbrl_facts")
        .select("accession_no")
        .eq("cik", ck)
        .limit(scan_limit)
        .execute()
    )
    seen_acc: list[str] = []
    for row in r.data or []:
        a = str(row.get("accession_no") or "")
        if a and a not in seen_acc:
            seen_acc.append(a)
    for acc in seen_acc:
        ex = (
            client.table("issuer_quarter_snapshots")
            .select("id")
            .eq("cik", ck)
            .eq("accession_no", acc)
            .limit(1)
            .execute()
        )
        if not ex.data:
            return acc
    return None


def report_quarter_snapshot_backfill_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if materialization_report is not None:
        mat = materialization_report
    else:
        mat = report_factor_panel_materialization_gaps(
            client,
            universe_name=universe_name,
            panel_limit=panel_limit,
            registry_report=registry_report,
        )
    bucket: list[dict[str, Any]] = list(
        (mat.get("materialization_buckets") or {}).get(
            "missing_quarter_snapshot_for_cik"
        )
        or []
    )
    by_class: dict[str, list[dict[str, Any]]] = {}
    classified_rows: list[dict[str, Any]] = []
    for row in bucket:
        cik = str(row.get("cik") or "").strip()
        sym = str(row.get("symbol") or "").strip()
        cls = classify_cik_quarter_snapshot_gap(client, cik=cik)
        rec = {"symbol": sym, "cik": cik, "norm_cik": row.get("norm_cik"), "class": cls}
        by_class.setdefault(cls, []).append(rec)
        classified_rows.append(rec)
    counts = {k: len(v) for k, v in sorted(by_class.items())}
    return {
        "ok": True,
        "universe_name": universe_name,
        "source_bucket_count": len(bucket),
        "missing_quarter_snapshot_bucket": bucket,
        "classification_counts": counts,
        "classification_rows": classified_rows,
        "classification_sample": {
            k: v[:25] for k, v in sorted(by_class.items())
        },
    }


def run_quarter_snapshot_backfill_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 25,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    rep = report_quarter_snapshot_backfill_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    bucket: list[dict[str, Any]] = list(
        rep.get("missing_quarter_snapshot_bucket") or []
    )
    actions: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    seen_cik: set[str] = set()
    for row in bucket:
        cik = str(row.get("cik") or "").strip()
        if not cik or cik in seen_cik:
            continue
        seen_cik.add(cik)
        cls = classify_cik_quarter_snapshot_gap(client, cik=cik)
        if cls != "silver_present_snapshot_materialization_missing":
            if len(deferred) < 200:
                deferred.append(
                    {"cik": cik, "symbol": row.get("symbol"), "class": cls}
                )
            continue
        if len(actions) >= max_cik_repairs:
            deferred.append(
                {
                    "cik": cik,
                    "symbol": row.get("symbol"),
                    "class": "deferred_repair_cap",
                }
            )
            continue
        acc = find_silver_accession_without_snapshot(client, cik=cik)
        if not acc:
            actions.append(
                {"cik": cik, "ok": False, "error": "no_silver_accession_without_snapshot"}
            )
            continue
        try:
            out = rebuild_quarter_snapshot_from_db(
                client, cik=cik, accession_no=acc
            )
            actions.append({"cik": cik, "accession_no": acc, "result": out})
        except Exception as ex:  # noqa: BLE001
            actions.append({"cik": cik, "accession_no": acc, "error": str(ex)})
    ok_n = sum(1 for a in actions if a.get("result", {}).get("ok"))
    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "quarter_snapshot_backfill",
        "cik_repairs_attempted": len(actions),
        "cik_repairs_succeeded": ok_n,
        "actions": actions,
        "deferred_sample": deferred[:80],
        "report_snapshot": rep.get("classification_counts"),
    }


def export_quarter_snapshot_backfill_targets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    rep = report_quarter_snapshot_backfill_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    flat: list[dict[str, Any]] = list(rep.get("classification_rows") or [])
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and flat:
        keys = sorted({k for row in flat for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)
    elif fmt == "csv":
        p.write_text("symbol,cik,class\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"ok": True, "path": str(p), "format": fmt}
