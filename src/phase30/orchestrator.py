"""Phase 30: filing index · silver · empty_cik 진단 후 좁은 하류 연쇄."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase30.downstream_cascade import run_downstream_substrate_cascade_for_ciks
from phase30.empty_cik_cleanup import run_empty_cik_cleanup_repair
from phase30.filing_index_gaps import (
    report_filing_index_gap_targets,
    run_filing_index_backfill_repair,
)
from phase30.metrics import collect_validation_substrate_snapshot
from phase30.phase31_recommend import recommend_phase31_branch
from phase30.silver_materialization import (
    report_silver_facts_materialization_gaps,
    run_silver_facts_materialization_repair,
)
from research_validation.metrics import norm_cik


def run_phase30_validation_substrate_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_filing_index_cik_repairs: int = 40,
    max_silver_materialization_cik_repairs: int = 10,
    max_downstream_ciks: int = 60,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    before = collect_validation_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    fi_preflight = report_filing_index_gap_targets(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    fi_rep = run_filing_index_backfill_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_filing_index_cik_repairs,
    )

    sil_preflight = report_silver_facts_materialization_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    sil_rep = run_silver_facts_materialization_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_silver_materialization_cik_repairs,
    )

    empty_rep = run_empty_cik_cleanup_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
    )

    touched: list[str] = []
    hints: dict[str, str] = {}

    for x in fi_rep.get("repaired_now") or []:
        cik = str(x.get("cik") or "").strip()
        if cik:
            touched.append(cik)
        sym = str(x.get("ticker") or x.get("symbol") or "").strip()
        if cik and sym:
            hints[cik] = sym

    for act in sil_rep.get("actions") or []:
        if act.get("skipped"):
            continue
        mo = act.get("materialize_silver") or {}
        if int(mo.get("silver_inserted") or 0) <= 0:
            continue
        cik = str(act.get("cik") or "").strip()
        if cik:
            touched.append(cik)
        sym = str(act.get("symbol") or "").strip()
        if cik and sym:
            hints[cik] = sym

    for row in empty_rep.get("deterministic_repairs_applied") or []:
        cik = str(row.get("cik") or "").strip()
        if cik:
            touched.append(cik)

    seen_n: set[str] = set()
    touched_uq: list[str] = []
    for cik in touched:
        nk = norm_cik(cik)
        if not nk or nk in seen_n:
            continue
        seen_n.add(nk)
        touched_uq.append(cik)
        if len(touched_uq) >= max_downstream_ciks:
            break

    cascade = run_downstream_substrate_cascade_for_ciks(
        settings,
        client,
        ciks=touched_uq,
        ticker_hints=hints,
    )

    after = collect_validation_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    p31 = recommend_phase31_branch(
        before=before,
        after=after,
        filing_repair=fi_rep,
        silver_repair=sil_rep,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "before": before,
        "after": after,
        "filing_index_gap_targets": fi_preflight,
        "filing_index_backfill_repair": fi_rep,
        "silver_facts_materialization_preflight": sil_preflight,
        "silver_facts_materialization_repair": sil_rep,
        "empty_cik_cleanup": empty_rep,
        "downstream_substrate_cascade": cascade,
        "phase31": p31,
    }
