"""Phase 36-B: 잔여 no_state_change_join 행 정밀 분류·상한 수리."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import bisect

from db import records as dbrec
from db.client import get_supabase_client
from public_depth.constants import DEFAULT_STATE_CHANGE_SCORES_LIMIT
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import (
    norm_cik,
    norm_signal_date,
    safe_float,
    state_change_rows_by_cik_sorted,
)
from state_change.runner import run_state_change


def _pick_state_change_with_reason(
    by_cik: dict[str, list[tuple[str, dict[str, Any]]]],
    *,
    cik: str,
    signal_date: str,
) -> tuple[dict[str, Any] | None, str]:
    ck = norm_cik(cik)
    pairs = by_cik.get(ck)
    if not pairs:
        return None, "state_change_not_built_for_row"
    dates = [p[0] for p in pairs]
    idx = bisect.bisect_right(dates, signal_date) - 1
    if idx < 0:
        return None, "state_change_built_but_join_key_mismatch"
    return pairs[idx][1], "picked"


def report_residual_state_change_join_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_scores_limit: int = DEFAULT_STATE_CHANGE_SCORES_LIMIT,
) -> dict[str, Any]:
    state_run_id = dbrec.fetch_latest_state_change_run_id(
        client, universe_name=universe_name
    )
    scores: list[dict[str, Any]] = []
    if state_run_id:
        scores = dbrec.fetch_state_change_scores_for_run(
            client, run_id=state_run_id, limit=state_change_scores_limit
        )
    sc_by_cik = state_change_rows_by_cik_sorted(scores)

    as_of = dbrec.fetch_max_as_of_universe(client, universe_name=universe_name)
    symbols = (
        dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe_name, as_of_date=as_of
        )
        if as_of
        else []
    )
    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=panel_limit
    )

    rows_out: list[dict[str, Any]] = []
    for p in panels:
        sym = str(p.get("symbol") or "").upper().strip()
        excess = safe_float(p.get(EXCESS_FIELD))
        if excess is None:
            continue
        cik = norm_cik(p.get("cik"))
        sig = norm_signal_date(p.get("signal_available_date"))
        if not cik or not sig:
            continue
        sc_row, seam = _pick_state_change_with_reason(
            sc_by_cik, cik=cik, signal_date=sig
        )
        if sc_row is not None:
            sc_score = safe_float(sc_row.get("state_change_score_v1"))
            if sc_score is not None:
                continue
            rows_out.append(
                {
                    "symbol": sym,
                    "cik": cik,
                    "accession_no": str(p.get("accession_no") or ""),
                    "factor_version": str(p.get("factor_version") or ""),
                    "signal_available_date": sig,
                    "residual_join_bucket": "state_change_built_but_as_of_or_pit_mismatch",
                    "blocked_reason": "missing_state_change_score_v1_after_pick",
                    "picked_state_change_as_of": str(sc_row.get("as_of_date") or "")[
                        :10
                    ],
                }
            )
            continue
        bucket = str(seam)
        if bucket == "picked":
            bucket = "other_residual_join_reason"
        br = bucket
        if bucket == "state_change_not_built_for_row":
            br = "no_state_change_rows_for_cik_in_loaded_run_window"
        elif bucket == "state_change_built_but_join_key_mismatch":
            br = "earliest_state_change_as_of_after_signal_no_pit_match"
        rows_out.append(
            {
                "symbol": sym,
                "cik": cik,
                "accession_no": str(p.get("accession_no") or ""),
                "factor_version": str(p.get("factor_version") or ""),
                "signal_available_date": sig,
                "residual_join_bucket": bucket,
                "blocked_reason": br,
                "first_state_change_as_of_in_run": (
                    sc_by_cik.get(cik, [])[0][0] if sc_by_cik.get(cik) else None
                ),
            }
        )

    counts: dict[str, int] = {}
    for r in rows_out:
        b = str(r.get("residual_join_bucket") or "")
        counts[b] = counts.get(b, 0) + 1

    _, excl = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    nsc_headline = int(excl.get("no_state_change_join") or 0)

    return {
        "ok": True,
        "universe_name": universe_name,
        "state_change_run_id": state_run_id,
        "state_change_scores_loaded": len(scores),
        "no_state_change_join_headline": nsc_headline,
        "residual_row_count": len(rows_out),
        "residual_join_bucket_counts": counts,
        "rows": rows_out,
    }


REPAIRABLE_RESIDUAL_BUCKETS = frozenset({"state_change_not_built_for_row"})


def run_residual_state_change_join_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_scores_limit: int = DEFAULT_STATE_CHANGE_SCORES_LIMIT,
    factor_version: str = "v1",
    max_state_change_issuers: int = 2500,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    before = report_residual_state_change_join_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
    )
    rows = list(before.get("rows") or [])
    targets = [
        r
        for r in rows
        if str(r.get("residual_join_bucket") or "") in REPAIRABLE_RESIDUAL_BUCKETS
    ]
    ciks = sorted({str(r.get("cik") or "") for r in targets} - {""})

    snap_before_m, ex0 = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    nsc0 = int(ex0.get("no_state_change_join") or 0)

    if not targets:
        snap_after_m, ex1 = snap_before_m, ex0
        return {
            "ok": True,
            "repair": "residual_state_change_join_repair",
            "skipped": True,
            "reason": "no_rows_in_repairable_residual_buckets",
            "repairable_bucket_allowlist": sorted(REPAIRABLE_RESIDUAL_BUCKETS),
            "report_before": before,
            "report_after": before,
            "no_state_change_join_cleared_now_count": 0,
            "residual_join_rows_still_blocked_count": len(rows),
            "state_change_run": {"skipped": True},
            "substrate_metrics_before": snap_before_m,
            "substrate_metrics_after": snap_after_m,
        }

    limit = min(
        max_state_change_issuers,
        max(200, 100 + 80 * len(ciks)),
    )
    sc_out = run_state_change(
        client,
        universe_name=universe_name,
        factor_version=factor_version,
        limit=limit,
        dry_run=False,
    )

    after = report_residual_state_change_join_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
    )
    snap_after_m, ex1 = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    nsc1 = int(ex1.get("no_state_change_join") or 0)
    rows_after = list(after.get("rows") or [])

    return {
        "ok": True,
        "repair": "residual_state_change_join_repair",
        "repair_target_row_count": len(targets),
        "distinct_ciks": ciks,
        "state_change_issuer_limit_used": limit,
        "state_change_run": sc_out,
        "report_before": before,
        "report_after": after,
        "no_state_change_join_cleared_now_count": max(0, nsc0 - nsc1),
        "residual_join_rows_still_blocked_count": len(rows_after),
        "substrate_metrics_before": snap_before_m,
        "substrate_metrics_after": snap_after_m,
    }


def export_residual_state_change_join_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int,
    state_change_scores_limit: int,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    rep = report_residual_state_change_join_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
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
        p.write_text("symbol,cik,residual_join_bucket\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**rep, "export_path": str(p.resolve())}
