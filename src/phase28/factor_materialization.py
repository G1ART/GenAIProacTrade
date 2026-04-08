"""레지스트리 `factor_panel_missing` / `validation_omission` 심볼을 스냅샷·패널 기준으로 세분."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from research_validation.metrics import norm_cik
from targeted_backfill.validation_registry import report_validation_registry_gaps

_BUCKET_NO_FACTOR = "factor_panel_missing_for_resolved_cik"
_BUCKET_VALIDATION_OMISSION = "validation_panel_build_omission_for_cik"


def report_factor_panel_materialization_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    reg = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    if not reg.get("ok"):
        return {**reg, "materialization_bucket_counts": {}, "materialization_buckets": {}}

    buckets_reg = reg.get("registry_buckets") or {}
    no_factor = list(buckets_reg.get(_BUCKET_NO_FACTOR, []))
    val_om = list(buckets_reg.get(_BUCKET_VALIDATION_OMISSION, []))

    as_of = (reg.get("metrics") or {}).get("as_of_date")
    if not as_of:
        return {
            "ok": True,
            "universe_name": universe_name,
            "panel_limit": panel_limit,
            "note": "no_as_of_date",
            "registry_bucket_counts": reg.get("registry_bucket_counts"),
            "materialization_bucket_counts": {},
            "materialization_buckets": {},
        }

    as_of_s = str(as_of)[:10]
    symbols_all = dbrec.fetch_symbols_universe_as_of(
        client, universe_name=universe_name, as_of_date=as_of_s
    )
    cik_by_symbol = dbrec.fetch_cik_map_for_tickers(client, symbols_all)
    lim = max(int(panel_limit), 50_000)

    missing_snap: list[dict[str, Any]] = []
    snap_no_panel: list[dict[str, Any]] = []
    for su in no_factor:
        raw = str(cik_by_symbol.get(su) or "").strip()
        nc = norm_cik(raw) if raw else ""
        if not raw:
            missing_snap.append(
                {"symbol": su, "cik": "", "norm_cik": "", "note": "no_cik_on_issuer_map"}
            )
            continue
        snaps = dbrec.fetch_issuer_quarter_snapshots_for_cik(client, cik=raw)
        if not snaps:
            missing_snap.append({"symbol": su, "cik": raw, "norm_cik": nc})
        else:
            snap_no_panel.append(
                {
                    "symbol": su,
                    "cik": raw,
                    "norm_cik": nc,
                    "n_snapshots": len(snaps),
                }
            )

    val_rows: list[dict[str, Any]] = []
    for su in val_om:
        raw = str(cik_by_symbol.get(su) or "").strip()
        nc = norm_cik(raw) if raw else ""
        if not raw:
            val_rows.append(
                {
                    "symbol": su,
                    "cik": "",
                    "norm_cik": "",
                    "n_factor_panels": 0,
                    "note": "no_cik_on_issuer_map",
                }
            )
            continue
        fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
            client, ciks=[raw], limit=lim
        )
        panels = [v for k, v in fmap.items() if str(k[0]).strip() == raw]
        val_rows.append(
            {
                "symbol": su,
                "cik": raw,
                "norm_cik": nc,
                "n_factor_panels": len(panels),
            }
        )

    with_panels = [x for x in val_rows if int(x.get("n_factor_panels") or 0) > 0]
    mat_buckets = {
        "missing_quarter_snapshot_for_cik": missing_snap,
        "snapshot_present_but_factor_panel_missing": snap_no_panel,
        "factor_panel_exists_but_validation_panel_missing": with_panels,
        "validation_panel_build_omission_for_existing_factor_panel": with_panels,
    }
    counts = {k: len(v) for k, v in mat_buckets.items()}
    return {
        "ok": True,
        "universe_name": universe_name,
        "panel_limit": panel_limit,
        "as_of_date": as_of_s,
        "registry_bucket_counts": reg.get("registry_bucket_counts"),
        "materialization_bucket_counts": counts,
        "materialization_buckets": mat_buckets,
        "materialization_buckets_sample": {
            k: v[:30] for k, v in mat_buckets.items()
        },
    }


def run_factor_panel_materialization_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_factor_cik_repairs: int = 40,
    max_validation_cik_repairs: int = 40,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    from factors.panel_build import run_factor_panels_for_cik
    from market.validation_panel_run import run_validation_panel_build_from_rows

    client = get_supabase_client(settings)
    before = report_factor_panel_materialization_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    factor_actions: list[dict[str, Any]] = []
    validation_actions: list[dict[str, Any]] = []

    snap_bucket = (
        before.get("materialization_buckets") or {}
    ).get("snapshot_present_but_factor_panel_missing") or []
    seen_cik: set[str] = set()
    for row in snap_bucket:
        cik = str(row.get("cik") or "").strip()
        if not cik or cik in seen_cik:
            continue
        if len(seen_cik) >= max_factor_cik_repairs:
            break
        seen_cik.add(cik)
        out = run_factor_panels_for_cik(
            client, cik, ticker_hint=str(row.get("symbol") or "")
        )
        factor_actions.append({"cik": cik, "symbol_hint": row.get("symbol"), "result": out})

    val_bucket = (
        before.get("materialization_buckets") or {}
    ).get("factor_panel_exists_but_validation_panel_missing") or []
    seen_v: set[str] = set()
    lim = max(int(panel_limit), 50_000)
    for row in val_bucket:
        cik = str(row.get("cik") or "").strip()
        if not cik or cik in seen_v:
            continue
        if len(seen_v) >= max_validation_cik_repairs:
            break
        seen_v.add(cik)
        fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
            client, ciks=[cik], limit=lim
        )
        panels = [v for k, v in fmap.items() if str(k[0]).strip() == cik]
        if not panels:
            validation_actions.append(
                {"cik": cik, "skipped": True, "reason": "no_factor_panels_after_prefetch"}
            )
            continue
        vout = run_validation_panel_build_from_rows(
            settings,
            panels=panels,
            metadata_json={
                "phase28": "factor_materialization_repair",
                "cik": cik,
                "universe_name": universe_name,
            },
        )
        validation_actions.append({"cik": cik, "n_panels": len(panels), "result": vout})

    after = report_factor_panel_materialization_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    return {
        "ok": True,
        "universe_name": universe_name,
        "before_materialization_bucket_counts": before.get(
            "materialization_bucket_counts"
        ),
        "after_materialization_bucket_counts": after.get("materialization_bucket_counts"),
        "factor_panel_repairs_attempted": len(factor_actions),
        "validation_panel_repairs_attempted": len(
            [a for a in validation_actions if not a.get("skipped")]
        ),
        "factor_actions": factor_actions,
        "validation_actions": validation_actions,
    }
