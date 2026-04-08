"""
`raw_present_no_silver_facts` 재시도: concept 매핑 정규화 후 silver·스냅샷·하류.

GIS 등 `us-gaap_Foo` 형태 미매핑은 `concept_map.normalize_concept_key_for_mapping` 로 해소.
"""

from __future__ import annotations

from typing import Any

from phase29.quarter_snapshot_gaps import (
    classify_cik_quarter_snapshot_gap,
    find_silver_accession_without_snapshot,
    report_quarter_snapshot_backfill_gaps,
)
from phase30.downstream_cascade import run_downstream_substrate_cascade_for_ciks
from phase30.silver_materialization import materialize_silver_from_raw_for_cik
from research_validation.metrics import norm_cik
from sec.facts.facts_pipeline import rebuild_quarter_snapshot_from_db


def report_raw_present_no_silver_targets(
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
        "targets": rows,
        "target_count": len(rows),
    }


def run_gis_like_silver_materialization_seam_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 5,
    prioritize_symbols: tuple[str, ...] = ("GIS",),
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    prep = report_raw_present_no_silver_targets(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    targets = list(prep.get("targets") or [])
    prio = {s.upper().strip() for s in prioritize_symbols if s}

    def _key(row: dict[str, Any]) -> tuple[int, str]:
        sym = str(row.get("symbol") or "").upper().strip()
        return (0 if sym in prio else 1, sym)

    targets.sort(key=_key)

    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    n = 0
    for row in targets:
        cik = str(row.get("cik") or "").strip()
        nk = norm_cik(cik) if cik else ""
        if not cik or not nk or nk in seen:
            continue
        seen.add(nk)
        if n >= max_cik_repairs:
            actions.append(
                {"cik": cik, "skipped": True, "reason": "repair_cap"}
            )
            continue
        n += 1
        cls_before = classify_cik_quarter_snapshot_gap(client, cik=cik)
        mat = materialize_silver_from_raw_for_cik(client, cik=cik)
        snap_out: dict[str, Any] = {}
        if int(mat.get("silver_inserted") or 0) > 0:
            acc = find_silver_accession_without_snapshot(client, cik=cik)
            if acc:
                try:
                    snap_out = rebuild_quarter_snapshot_from_db(
                        client, cik=cik, accession_no=acc
                    )
                except Exception as ex:  # noqa: BLE001
                    snap_out = {"ok": False, "error": str(ex)}
        cls_after = classify_cik_quarter_snapshot_gap(client, cik=cik)
        sym = str(row.get("symbol") or "").strip()
        cascade = run_downstream_substrate_cascade_for_ciks(
            settings,
            client,
            ciks=[cik],
            ticker_hints={cik: sym} if sym else {},
            max_snapshot_repairs_per_cik=5,
        )
        actions.append(
            {
                "cik": cik,
                "symbol": row.get("symbol"),
                "classification_before": cls_before,
                "materialize_silver": mat,
                "quarter_snapshot_rebuild": snap_out,
                "classification_after": cls_after,
                "downstream_cascade": cascade,
            }
        )

    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "gis_like_silver_seam",
        "actions": actions,
        "preflight": prep,
    }
