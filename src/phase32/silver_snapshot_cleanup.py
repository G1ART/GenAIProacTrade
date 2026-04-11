"""`silver_present_snapshot_materialization_missing` 및 GIS-like raw→silver 좁은 수리."""

from __future__ import annotations

from typing import Any

from phase28.factor_materialization import report_factor_panel_materialization_gaps
from phase29.quarter_snapshot_gaps import (
    classify_cik_quarter_snapshot_gap,
    find_silver_accession_without_snapshot,
    report_quarter_snapshot_backfill_gaps,
)
from phase30.downstream_cascade import run_downstream_substrate_cascade_for_ciks
from phase31.silver_seam_repair import run_gis_like_silver_materialization_seam_repair
from research_validation.metrics import norm_cik
from sec.facts.facts_pipeline import rebuild_quarter_snapshot_from_db
from targeted_backfill.validation_registry import report_validation_registry_gaps


def report_silver_present_snapshot_materialization_targets(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    reg = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    mat = report_factor_panel_materialization_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=reg,
    )
    qrep = report_quarter_snapshot_backfill_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=reg,
        materialization_report=mat,
    )
    rows = [
        dict(r)
        for r in (qrep.get("classification_rows") or [])
        if str(r.get("class") or "") == "silver_present_snapshot_materialization_missing"
    ]
    return {
        "ok": True,
        "universe_name": universe_name,
        "targets": rows,
        "target_count": len(rows),
        "quarter_snapshot_report": qrep,
    }


def run_silver_present_snapshot_materialization_repair(
    settings: Any,
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_cik_repairs: int = 15,
    max_snapshot_repairs_per_cik: int = 5,
) -> dict[str, Any]:
    prep = report_silver_present_snapshot_materialization_targets(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    targets = list(prep.get("targets") or [])
    seen: set[str] = set()
    actions: list[dict[str, Any]] = []
    n = 0
    for row in targets:
        cik = str(row.get("cik") or "").strip()
        nk = norm_cik(cik) if cik else ""
        if not cik or not nk or nk in seen:
            continue
        seen.add(nk)
        if n >= max_cik_repairs:
            actions.append({"cik": cik, "skipped": True, "reason": "repair_cap"})
            continue
        n += 1
        cls_before = classify_cik_quarter_snapshot_gap(client, cik=cik)
        sym = str(row.get("symbol") or "").strip()
        snap_actions: list[dict[str, Any]] = []
        for _ in range(max_snapshot_repairs_per_cik):
            acc = find_silver_accession_without_snapshot(client, cik=cik, scan_limit=400)
            if not acc:
                break
            try:
                r = rebuild_quarter_snapshot_from_db(
                    client, cik=cik, accession_no=acc
                )
            except Exception as ex:  # noqa: BLE001
                r = {"ok": False, "error": str(ex)}
            snap_actions.append({"accession_no": acc, "result": r})
            if not r.get("ok"):
                break
        cascade = run_downstream_substrate_cascade_for_ciks(
            settings,
            client,
            ciks=[cik],
            ticker_hints={cik: sym} if sym else {},
            max_snapshot_repairs_per_cik=0,
        )
        cls_after = classify_cik_quarter_snapshot_gap(client, cik=cik)
        actions.append(
            {
                "cik": cik,
                "symbol": row.get("symbol"),
                "classification_before": cls_before,
                "classification_after": cls_after,
                "snapshot_repairs": snap_actions,
                "downstream_cascade": cascade,
                "snapshot_materialized_now": cls_before
                == "silver_present_snapshot_materialization_missing"
                and cls_after != "silver_present_snapshot_materialization_missing",
            }
        )
    cleared = sum(1 for a in actions if a.get("snapshot_materialized_now"))
    return {
        "ok": True,
        "repair": "silver_present_snapshot_materialization_missing",
        "actions": actions,
        "snapshot_materialized_now_count": cleared,
        "targets_considered": len([a for a in actions if not a.get("skipped")]),
    }


def run_gis_raw_present_no_silver_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    """GIS 우선 1건 — phase31과 동일 결정적 materialize 경로."""
    return run_gis_like_silver_materialization_seam_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=1,
        prioritize_symbols=("GIS",),
    )
