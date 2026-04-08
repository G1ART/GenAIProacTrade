"""`raw_present_no_silver_facts`: raw→silver 적재 및 스냅샷 재구성."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from phase29.quarter_snapshot_gaps import (
    classify_cik_quarter_snapshot_gap,
    find_silver_accession_without_snapshot,
    report_quarter_snapshot_backfill_gaps,
)
from sec.facts.facts_pipeline import rebuild_quarter_snapshot_from_db
from sec.facts.normalize_facts import raw_dict_to_silver_candidate


def _distinct_accessions_raw(client: Any, *, cik: str) -> list[str]:
    r = (
        client.table("raw_xbrl_facts")
        .select("accession_no")
        .eq("cik", cik)
        .limit(2000)
        .execute()
    )
    seen: list[str] = []
    s: set[str] = set()
    for row in r.data or []:
        a = str(row.get("accession_no") or "").strip()
        if a and a not in s:
            s.add(a)
            seen.append(a)
    return seen


def materialize_silver_from_raw_for_cik(
    client: Any,
    *,
    cik: str,
    revision_no: int = 1,
) -> dict[str, Any]:
    accs = _distinct_accessions_raw(client, cik=cik)
    inserted = 0
    skipped = 0
    unmapped_raw = 0
    for acc in accs:
        raw_rows = dbrec.fetch_raw_xbrl_facts_for_filing(
            client, cik=cik, accession_no=acc
        )
        for raw in raw_rows:
            silver = raw_dict_to_silver_candidate(raw, revision_no=revision_no)
            if not silver:
                unmapped_raw += 1
                continue
            if dbrec.silver_xbrl_fact_exists(
                client,
                cik=cik,
                accession_no=acc,
                canonical_concept=silver["canonical_concept"],
                revision_no=revision_no,
                fact_period_key=silver["fact_period_key"],
            ):
                skipped += 1
                continue
            dbrec.insert_silver_xbrl_fact(client, silver)
            inserted += 1
    return {
        "cik": cik,
        "accession_count": len(accs),
        "silver_inserted": inserted,
        "silver_skipped_existing": skipped,
        "raw_rows_unmapped_to_silver": unmapped_raw,
    }


def report_silver_facts_materialization_gaps(
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
        if str(r.get("class") or "") == "raw_present_no_silver_facts"
    ]
    return {
        "ok": True,
        "universe_name": universe_name,
        "raw_present_no_silver_facts_count": len(rows),
        "targets": rows,
    }


def run_silver_facts_materialization_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 10,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    prep = report_silver_facts_materialization_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    targets = list(prep.get("targets") or [])
    actions: list[dict[str, Any]] = []
    seen_cik: set[str] = set()
    repair_n = 0
    for row in targets:
        cik = str(row.get("cik") or "").strip()
        if not cik or cik in seen_cik:
            continue
        seen_cik.add(cik)
        if repair_n >= max_cik_repairs:
            actions.append({"cik": cik, "skipped": True, "reason": "repair_cap"})
            continue
        repair_n += 1
        cls_before = "raw_present_no_silver_facts"
        mat_out = materialize_silver_from_raw_for_cik(client, cik=cik)
        snap_followup: dict[str, Any] = {}
        new_class = classify_cik_quarter_snapshot_gap(client, cik=cik)
        if int(mat_out.get("silver_inserted") or 0) > 0:
            acc = find_silver_accession_without_snapshot(client, cik=cik)
            if acc:
                try:
                    snap_followup = rebuild_quarter_snapshot_from_db(
                        client, cik=cik, accession_no=acc
                    )
                except Exception as ex:  # noqa: BLE001
                    snap_followup = {"ok": False, "error": str(ex)}
            new_class = classify_cik_quarter_snapshot_gap(client, cik=cik)
        actions.append(
            {
                "cik": cik,
                "symbol": row.get("symbol"),
                "materialize_silver": mat_out,
                "classification_before": cls_before,
                "classification_after": new_class,
                "quarter_snapshot_rebuild": snap_followup,
            }
        )
    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "silver_facts_materialization",
        "max_cik_repairs": max_cik_repairs,
        "cik_repairs_attempted": repair_n,
        "actions": actions,
        "preflight": prep,
    }
