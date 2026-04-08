"""수리된 CIK에만 분기 스냅샷→팩터→검증 패널 최소 연쇄."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from factors.panel_build import run_factor_panels_for_cik
from market.validation_panel_run import run_validation_panel_build_from_rows
from phase29.quarter_snapshot_gaps import (
    find_silver_accession_without_snapshot,
    rebuild_quarter_snapshot_from_db,
)


def run_downstream_substrate_cascade_for_ciks(
    settings: Any,
    client: Any,
    *,
    ciks: list[str],
    ticker_hints: dict[str, str] | None = None,
    max_snapshot_repairs_per_cik: int = 5,
) -> dict[str, Any]:
    hints = ticker_hints or {}
    per_cik: list[dict[str, Any]] = []
    for raw_cik in ciks:
        cik = str(raw_cik).strip()
        if not cik:
            continue
        hint = str(hints.get(cik) or "").strip() or None
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
        fac = run_factor_panels_for_cik(
            client, cik, ticker_hint=hint, record_run=True
        )
        lim = 50_000
        fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
            client, ciks=[cik], limit=lim
        )
        panels = [v for k, v in fmap.items() if str(k[0]).strip() == cik]
        val: dict[str, Any] = {"skipped": True, "reason": "no_factor_panels"}
        if panels:
            val = run_validation_panel_build_from_rows(
                settings,
                panels=panels,
                metadata_json={
                    "phase30": "downstream_substrate_cascade",
                    "cik": cik,
                },
            )
        per_cik.append(
            {
                "cik": cik,
                "snapshot_repairs": snap_actions,
                "factor_panel": fac,
                "validation_panel": val,
            }
        )
    return {"ok": True, "cik_count": len(per_cik), "per_cik": per_cik}
