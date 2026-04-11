"""Phase 36-A: Phase 35 신규 joined 23행 대상 market_metadata 플래그 정합."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from db.client import get_supabase_client
from market.validation_panel_run import run_validation_panel_build_from_rows
from market.price_ingest import run_market_metadata_hydration_for_symbols
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.metrics import norm_cik, norm_signal_date

from phase36.phase35_bundle_io import (
    load_phase35_bundle,
    natural_key_from_reference,
    newly_joined_references_from_phase35,
)


def _joined_row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        norm_cik(row.get("cik")),
        str(row.get("accession_no") or ""),
        str(row.get("factor_version") or ""),
        norm_signal_date(row.get("signal_available_date")),
    )


def _panel_has_missing_market_metadata_flag(row: dict[str, Any]) -> bool:
    pj = row.get("panel_json") if isinstance(row.get("panel_json"), dict) else {}
    flags = pj.get("quality_flags") or []
    if not isinstance(flags, list):
        return False
    return "missing_market_metadata" in {str(x) for x in flags}


def _classify_reconciliation_bucket(
    row: dict[str, Any],
    *,
    client: Any,
    registry_by_sym: dict[str, dict[str, Any]],
    meta_by_sym: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    sym = str(row.get("symbol") or "").upper().strip()
    sig = norm_signal_date(row.get("signal_available_date"))

    if sym not in registry_by_sym:
        return "other_join_metadata_seam", "missing_market_symbol_registry_link"

    fm = meta_by_sym.get(sym)
    asof_s = str(fm.get("as_of_date") or "")[:10] if fm else ""
    if not fm or len(asof_s) < 10:
        return "true_missing_market_metadata", "no_market_metadata_row_or_empty_as_of"

    if sig and asof_s < sig:
        return "metadata_visible_but_not_selected", "metadata_as_of_before_signal_date"

    if _panel_has_missing_market_metadata_flag(row):
        return "stale_metadata_flag_after_join", "panel_json_stale_missing_market_metadata"

    return "other_join_metadata_seam", "flag_cleared_or_unexpected_state"


def report_joined_metadata_flag_reconciliation_targets(
    client: Any,
    *,
    universe_name: str,
    phase35_bundle: dict[str, Any] | None = None,
    phase35_bundle_path: str | None = None,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    if phase35_bundle is None:
        if not phase35_bundle_path:
            raise ValueError("phase35_bundle or phase35_bundle_path required")
        phase35_bundle = load_phase35_bundle(phase35_bundle_path)

    refs = newly_joined_references_from_phase35(phase35_bundle)

    joined: list[dict[str, Any]] = []
    compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        joined_panels_out=joined,
    )
    by_key = {_joined_row_key(r): r for r in joined}

    syms = sorted(
        {
            str(ref.get("symbol") or "").upper().strip()
            for ref in refs
            if ref.get("symbol")
        }
    )
    registry_by_sym = dbrec.fetch_market_symbol_registry_rows_for_symbols(client, syms)
    meta_by_sym = dbrec.fetch_market_metadata_latest_rows_for_symbols(client, syms)

    rows_out: list[dict[str, Any]] = []
    for ref in refs:
        k = natural_key_from_reference(ref)
        sym = str(ref.get("symbol") or "").upper().strip()
        live = by_key.get(k)
        if not live:
            rows_out.append(
                {
                    "symbol": sym,
                    "cik": k[0],
                    "accession_no": k[1],
                    "factor_version": k[2],
                    "signal_available_date": k[3],
                    "in_joined_substrate": False,
                    "has_metadata_flag": False,
                    "reconciliation_bucket": "other_join_metadata_seam",
                    "detail": "not_in_joined_substrate",
                }
            )
            continue
        bucket, detail = _classify_reconciliation_bucket(
            live,
            client=client,
            registry_by_sym=registry_by_sym,
            meta_by_sym=meta_by_sym,
        )
        rows_out.append(
            {
                "symbol": sym,
                "cik": k[0],
                "accession_no": k[1],
                "factor_version": k[2],
                "signal_available_date": k[3],
                "in_joined_substrate": True,
                "has_metadata_flag": _panel_has_missing_market_metadata_flag(live),
                "reconciliation_bucket": bucket,
                "detail": detail,
            }
        )

    flagged = [r for r in rows_out if r.get("has_metadata_flag")]
    counts: dict[str, int] = {}
    for r in rows_out:
        b = str(r.get("reconciliation_bucket") or "")
        counts[b] = counts.get(b, 0) + 1

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase35_newly_joined_target_count": len(refs),
        "rows": rows_out,
        "metadata_flagged_in_target_set_count": len(flagged),
        "reconciliation_bucket_counts": counts,
    }


def run_joined_metadata_reconciliation_repair_two_pass(
    settings: Any,
    *,
    universe_name: str,
    phase35_bundle_path: str,
    panel_limit: int = 8000,
    max_validation_rebuilds: int = 60,
) -> dict[str, Any]:
    """
    1) report_before 2) hydration 3) report_mid 4) stale 행만 validation rebuild
    5) report_after — Phase 36에서 드러난 시퀀싱 갭(수화만 하고 stale 재빌드 없음)을 한 런에서 닫는다.
    """
    client = get_supabase_client(settings)
    bundle = load_phase35_bundle(phase35_bundle_path)

    before_rep = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle=bundle,
        panel_limit=panel_limit,
    )
    rows = list(before_rep.get("rows") or [])
    before_flagged = sum(1 for r in rows if r.get("has_metadata_flag"))

    true_missing_syms = sorted(
        {
            str(r.get("symbol") or "").upper().strip()
            for r in rows
            if str(r.get("reconciliation_bucket") or "")
            == "true_missing_market_metadata"
            and r.get("symbol")
        }
    )
    asof_syms = sorted(
        {
            str(r.get("symbol") or "").upper().strip()
            for r in rows
            if str(r.get("reconciliation_bucket") or "")
            == "metadata_visible_but_not_selected"
            and r.get("symbol")
        }
    )

    hydration_syms = sorted(set(true_missing_syms) | set(asof_syms))
    hydration_out: dict[str, Any] = {"skipped": True}
    if hydration_syms:
        hydration_out = run_market_metadata_hydration_for_symbols(
            settings,
            universe_name=universe_name,
            symbols=hydration_syms,
        )

    mid_rep = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle=bundle,
        panel_limit=panel_limit,
    )
    mid_rows = list(mid_rep.get("rows") or [])

    stale_for_rebuild = [
        r
        for r in mid_rows
        if str(r.get("reconciliation_bucket") or "") == "stale_metadata_flag_after_join"
        and r.get("cik")
        and r.get("accession_no")
        and r.get("factor_version")
    ]
    validation_rebuild_target_count_after_hydration = len(stale_for_rebuild)

    factor_panels: list[dict[str, Any]] = []
    seen_fp: set[tuple[str, str, str]] = set()
    for r in stale_for_rebuild[: max(0, int(max_validation_rebuilds))]:
        ck = str(r.get("cik") or "")
        acc = str(r.get("accession_no") or "")
        fv = str(r.get("factor_version") or "")
        key = (ck, acc, fv)
        if not all(key) or key in seen_fp:
            continue
        seen_fp.add(key)
        fp = dbrec.fetch_issuer_quarter_factor_panel_one(
            client, cik=ck, accession_no=acc, factor_version=fv
        )
        if fp:
            factor_panels.append(fp)

    build_out: dict[str, Any] = {"status": "skipped", "rows_upserted": 0}
    if factor_panels:
        build_out = run_validation_panel_build_from_rows(
            settings,
            panels=factor_panels,
            metadata_json={
                "phase36": "joined_metadata_reconciliation_repair_two_pass",
                "universe_name": universe_name,
                "n_panels": len(factor_panels),
            },
        )

    after_rep = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle=bundle,
        panel_limit=panel_limit,
    )
    rows_after = list(after_rep.get("rows") or [])
    after_flagged = sum(1 for r in rows_after if r.get("has_metadata_flag"))
    cleared = max(0, before_flagged - after_flagged)

    return {
        "ok": True,
        "repair": "joined_metadata_reconciliation_repair_two_pass",
        "universe_name": universe_name,
        "metadata_flags_cleared_now_count": cleared,
        "metadata_flags_still_present_count": after_flagged,
        "targets_flagged_before": before_flagged,
        "hydration": hydration_out,
        "report_before": before_rep,
        "report_mid": mid_rep,
        "validation_rebuild_target_count_after_hydration": (
            validation_rebuild_target_count_after_hydration
        ),
        "validation_rebuild_factor_panels_submitted": len(factor_panels),
        "validation_rebuild": build_out,
        "report_after": after_rep,
    }


def run_joined_metadata_reconciliation_repair(
    settings: Any,
    *,
    universe_name: str,
    phase35_bundle_path: str,
    panel_limit: int = 8000,
    max_validation_rebuilds: int = 60,
) -> dict[str, Any]:
    """기존 CLI 호환: 내부적으로 항상 2패스(수화 → mid → stale 재빌드 → after)."""
    return run_joined_metadata_reconciliation_repair_two_pass(
        settings,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
        max_validation_rebuilds=max_validation_rebuilds,
    )


def export_joined_metadata_flag_reconciliation_targets(
    client: Any,
    *,
    universe_name: str,
    phase35_bundle_path: str,
    panel_limit: int,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    rep = report_joined_metadata_flag_reconciliation_targets(
        client,
        universe_name=universe_name,
        phase35_bundle_path=phase35_bundle_path,
        panel_limit=panel_limit,
    )
    rows = list(rep.get("rows") or [])
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and rows:
        keys = sorted({k for row in rows for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    elif fmt == "csv":
        p.write_text(
            "symbol,cik,accession_no,factor_version,signal_available_date\n",
            encoding="utf-8",
        )
    else:
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**rep, "export_path": str(p.resolve())}
