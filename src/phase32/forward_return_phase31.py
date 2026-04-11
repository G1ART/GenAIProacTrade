"""Phase 31 터치 집합에 한정한 forward-return 갭 리포트·백필."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from db import records as dbrec
from market.forward_returns_run import run_forward_returns_build_from_rows
from phase32.phase31_bundle_io import (
    load_phase31_bundle,
    phase31_touched_cik_list,
    phase31_touched_norm_ciks,
)
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import norm_cik, norm_signal_date, safe_float

# 진단 버킷 → 운영자용 병목 분류(워크오더 A)
_BUCKET_TO_BLOCKAGE: dict[str, str] = {
    "no_forward_row_next_quarter": "build_not_attempted_or_no_forward_row",
    "forward_row_missing_raw_return": "attempted_or_row_exists_raw_null_price_gap",
    "excess_null_despite_forward_row": "forward_row_present_excess_pipeline_gap",
    "missing_signal_date_on_panel": "as_of_or_signal_date_seam",
    "panel_stale_or_validation_refresh_needed": "validation_refresh_or_stale_panel",
}


def _blockage_for_bucket(bucket: str) -> str:
    return _BUCKET_TO_BLOCKAGE.get(bucket, "other_or_unknown")


def _classify_panel_forward_gap(
    client: Any, *, panel: dict[str, Any]
) -> tuple[str, str]:
    """(diagnose_bucket, blockage_class)."""
    sym = str(panel.get("symbol") or "").upper().strip()
    sig = norm_signal_date(panel.get("signal_available_date"))
    acc = str(panel.get("accession_no") or "")
    ck = norm_cik(panel.get("cik"))
    if not sig:
        return "missing_signal_date_on_panel", _blockage_for_bucket(
            "missing_signal_date_on_panel"
        )
    fr = dbrec.fetch_forward_return_for_signal(
        client,
        symbol=sym,
        signal_date=sig,
        horizon_type="next_quarter",
    )
    if not fr:
        return "no_forward_row_next_quarter", _blockage_for_bucket(
            "no_forward_row_next_quarter"
        )
    if fr.get("raw_forward_return") is None:
        return "forward_row_missing_raw_return", _blockage_for_bucket(
            "forward_row_missing_raw_return"
        )
    if fr.get("excess_forward_return") is None:
        return "excess_null_despite_forward_row", _blockage_for_bucket(
            "excess_null_despite_forward_row"
        )
    return "panel_stale_or_validation_refresh_needed", _blockage_for_bucket(
        "panel_stale_or_validation_refresh_needed"
    )


def report_forward_return_gap_targets_after_phase31(
    client: Any,
    *,
    bundle: dict[str, Any] | None = None,
    bundle_path: str | None = None,
    universe_name: str,
    panel_limit: int = 8000,
    max_target_ciks: int = 80,
) -> dict[str, Any]:
    if bundle is None:
        if not bundle_path:
            raise ValueError("bundle or bundle_path required")
        bundle = load_phase31_bundle(bundle_path)
    touched_list = phase31_touched_cik_list(bundle)[:max_target_ciks]
    touched_norm = phase31_touched_norm_ciks(bundle)

    queues: dict[str, list[str]] = {}
    cov, excl = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    miss_excess_syms = {s.upper().strip() for s in queues.get("missing_excess_return_1q", [])}

    target_entries: list[dict[str, Any]] = []
    for raw_cik in touched_list:
        cik = str(raw_cik).strip()
        nk = norm_cik(cik)
        sym = dbrec.fetch_ticker_for_cik(client, cik=cik)
        sym_u = str(sym or "").upper().strip()
        base = {
            "cik": cik,
            "cik_norm": nk,
            "symbol": sym_u or None,
            "in_phase31_touched": nk in touched_norm,
            "in_missing_excess_return_1q_queue": bool(sym_u and sym_u in miss_excess_syms),
        }
        if not sym_u:
            base["diagnose_bucket"] = "registry_seam_no_ticker_for_cik"
            base["blockage_class"] = "symbol_normalization_or_registry_seam"
            target_entries.append(base)
            continue
        if sym_u not in miss_excess_syms:
            base["diagnose_bucket"] = "not_in_missing_excess_queue"
            base["blockage_class"] = "coverage_queue_mismatch_or_already_forward_ok"
            target_entries.append(base)
            continue
        panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
            client, symbols=[sym_u], limit=min(panel_limit, 2000)
        )
        gap_panels = [p for p in panels if safe_float(p.get(EXCESS_FIELD)) is None]
        if not gap_panels:
            base["diagnose_bucket"] = "no_validation_rows_missing_excess_locally"
            base["blockage_class"] = "panel_stale_or_validation_refresh_needed"
            target_entries.append(base)
            continue
        for p in gap_panels[:5]:
            bkt, blk = _classify_panel_forward_gap(client, panel=p)
            target_entries.append(
                {
                    **base,
                    "accession_no": str(p.get("accession_no") or ""),
                    "signal_available_date": norm_signal_date(
                        p.get("signal_available_date")
                    ),
                    "diagnose_bucket": bkt,
                    "blockage_class": blk,
                }
            )

    bucket_counts: dict[str, int] = defaultdict(int)
    blockage_counts: dict[str, int] = defaultdict(int)
    for e in target_entries:
        bucket_counts[str(e.get("diagnose_bucket") or "")] += 1
        blockage_counts[str(e.get("blockage_class") or "")] += 1

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase31_touched_cik_count": len(touched_list),
        "metrics": cov,
        "exclusion_distribution": dict(excl),
        "missing_excess_return_1q_queue_size": len(miss_excess_syms),
        "target_entries": target_entries,
        "diagnose_bucket_counts": dict(bucket_counts),
        "blockage_class_counts": dict(blockage_counts),
    }


def export_forward_return_gap_targets_after_phase31(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    return str(p.resolve())


def _collect_factor_panels_for_cik_accession(
    client: Any,
    *,
    cik_acc: set[tuple[str, str]],
    panel_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not cik_acc:
        return [], {"panel_rows": 0, "distinct_cik_accession": 0}
    ciks = sorted({a[0] for a in cik_acc})
    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=ciks, limit=max(panel_limit, 50_000)
    )
    panels: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for key, prow in factor_map.items():
        ck = norm_cik(key[0])
        acc = str(key[1])
        if (ck, acc) in cik_acc and key not in seen:
            seen.add(key)
            panels.append(prow)
    meta = {
        "distinct_cik_accession": len(cik_acc),
        "panel_rows": len(panels),
    }
    return panels, meta


def run_forward_return_backfill_for_phase31_touched(
    settings: Any,
    *,
    bundle: dict[str, Any] | None = None,
    bundle_path: str | None = None,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_target_ciks: int = 30,
) -> dict[str, Any]:
    """Phase 31 터치 CIK 중 `missing_excess_return_1q` 큐에 있는 심볼만 상한으로 백필."""
    from db.client import get_supabase_client

    if bundle is None:
        if not bundle_path:
            raise ValueError("bundle or bundle_path required")
        bundle = load_phase31_bundle(bundle_path)

    client = get_supabase_client(settings)
    gap_rep = report_forward_return_gap_targets_after_phase31(
        client,
        bundle=bundle,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_target_ciks=max_target_ciks,
    )

    cik_acc: set[tuple[str, str]] = set()
    symbols_for_status: set[str] = set()
    for e in gap_rep.get("target_entries") or []:
        if str(e.get("diagnose_bucket") or "") != "no_forward_row_next_quarter":
            continue
        ck = norm_cik(e.get("cik"))
        acc = str(e.get("accession_no") or "")
        su = str(e.get("symbol") or "").upper().strip()
        if ck and acc:
            cik_acc.add((ck, acc))
        if su:
            symbols_for_status.add(su)

    per_symbol_before: dict[str, Any] = {}
    for sym in sorted(symbols_for_status):
        panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
            client, symbols=[sym], limit=50
        )
        p0 = next((p for p in panels if safe_float(p.get(EXCESS_FIELD)) is None), None)
        if not p0:
            per_symbol_before[sym] = {"note": "no_gap_panel_sampled"}
            continue
        sig = norm_signal_date(p0.get("signal_available_date"))
        if not sig:
            per_symbol_before[sym] = {"status": "blocked_signal_date"}
            continue
        fr = dbrec.fetch_forward_return_for_signal(
            client,
            symbol=sym,
            signal_date=sig,
            horizon_type="next_quarter",
        )
        per_symbol_before[sym] = {
            "accession_no": str(p0.get("accession_no") or ""),
            "has_forward_row": bool(fr),
            "raw_forward_return": fr.get("raw_forward_return") if fr else None,
            "excess_forward_return": fr.get("excess_forward_return") if fr else None,
            "signal_date": sig,
        }

    panels, pan_meta = _collect_factor_panels_for_cik_accession(
        client, cik_acc=cik_acc, panel_limit=panel_limit
    )
    build_out: dict[str, Any] = {"skipped": True, "reason": "no_panels_for_no_forward_rows"}
    if panels:
        build_out = run_forward_returns_build_from_rows(
            settings,
            panels=panels,
            metadata_json={
                "phase32": "forward_return_backfill_phase31_touched",
                "universe_name": universe_name,
                **pan_meta,
            },
            price_lookahead_days=price_lookahead_days,
        )
        build_out["skipped"] = False

    err_list: list[dict[str, Any]] = (
        build_out["error_sample"] if isinstance(build_out.get("error_sample"), list) else []
    )
    deferred_market = 0
    blocked_registry = 0
    for err in err_list:
        msg = str(err.get("error") or "")
        if "insufficient_price" in msg:
            deferred_market += 1
        else:
            blocked_registry += 1

    fail_n = int(build_out.get("failures") or 0)
    ok_ops = int(build_out.get("success_operations") or 0)
    if fail_n and not err_list:
        blocked_registry = fail_n

    per_symbol_after: dict[str, Any] = {}
    repaired_to_forward_present = 0
    for sym in sorted(symbols_for_status):
        before = per_symbol_before.get(sym) or {}
        sig_b = before.get("signal_date")
        if not sig_b:
            per_symbol_after[sym] = {"note": "no_baseline_signal"}
            continue
        fr = dbrec.fetch_forward_return_for_signal(
            client,
            symbol=sym,
            signal_date=sig_b,
            horizon_type="next_quarter",
        )
        ex = fr.get("excess_forward_return") if fr else None
        ex_before = before.get("excess_forward_return")
        per_symbol_after[sym] = {
            "excess_forward_return": ex,
            "forward_return_unblocked_now": safe_float(ex) is not None
            and safe_float(ex_before) is None,
        }
        if per_symbol_after[sym]["forward_return_unblocked_now"]:
            repaired_to_forward_present += 1

    return {
        "ok": True,
        "universe_name": universe_name,
        "forward_gap_report": gap_rep,
        "panels_built": len(panels),
        "cik_accession_pairs": len(cik_acc),
        "forward_build": build_out,
        "per_symbol_before": per_symbol_before,
        "per_symbol_after": per_symbol_after,
        "repaired_to_forward_present": repaired_to_forward_present,
        "deferred_market_data_gap": deferred_market,
        "blocked_registry_or_time_window_issue": blocked_registry,
        "build_success_operations": ok_ops,
        "build_failures": fail_n,
        "error_sample_bucket_note": "deferred/blocked_counts_from_error_sample_when_present",
    }
