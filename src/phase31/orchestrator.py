"""Phase 31: raw_xbrl 브리지 · silver 이음새 · issuer 결정적 수리 · 하류 연쇄."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase30.downstream_cascade import run_downstream_substrate_cascade_for_ciks
from phase30.metrics import collect_validation_substrate_snapshot
from phase31.issuer_mapping_repair import run_deterministic_empty_cik_issuer_repair
from phase31.phase32_recommend import recommend_phase32_branch
from phase31.raw_facts_gaps import report_raw_facts_gap_targets
from phase31.raw_facts_repair import run_raw_facts_backfill_repair
from phase31.silver_seam_repair import run_gis_like_silver_materialization_seam_repair
from research_validation.metrics import norm_cik


def run_phase31_raw_facts_bridge_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
    max_raw_facts_cik_repairs: int = 45,
    max_silver_seam_cik_repairs: int = 5,
    max_downstream_ciks: int = 80,
    max_empty_cik_symbol_repairs: int = 20,
    extra_raw_gap_ciks: list[str] | None = None,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    before = collect_validation_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    raw_preflight = report_raw_facts_gap_targets(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        extra_ciks=extra_raw_gap_ciks,
    )
    raw_rep = run_raw_facts_backfill_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_raw_facts_cik_repairs,
        extra_ciks=extra_raw_gap_ciks,
    )

    silver_seam = run_gis_like_silver_materialization_seam_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        max_cik_repairs=max_silver_seam_cik_repairs,
    )

    issuer_rep = run_deterministic_empty_cik_issuer_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbols_limit=max_empty_cik_symbol_repairs,
    )

    cascade_ciks: list[str] = []
    hints: dict[str, str] = {}
    seen_n: set[str] = set()

    for e in raw_rep.get("repaired_to_raw_present") or []:
        cik = str(e.get("cik") or "").strip()
        if not cik:
            continue
        nk = norm_cik(cik)
        if nk in seen_n:
            continue
        seen_n.add(nk)
        cascade_ciks.append(cik)
        t = str(e.get("ticker") or e.get("symbol") or "").strip()
        if t:
            hints[cik] = t

    for row in issuer_rep.get("deterministic_repairs_applied") or []:
        cik = str(row.get("cik") or "").strip()
        sym = str(row.get("symbol") or "").strip()
        if cik and norm_cik(cik) not in seen_n:
            seen_n.add(norm_cik(cik))
            cascade_ciks.append(cik)
        if cik and sym:
            hints[cik] = sym

    cascade_ciks_uq = cascade_ciks[:max_downstream_ciks]
    downstream_retry = run_downstream_substrate_cascade_for_ciks(
        settings,
        client,
        ciks=cascade_ciks_uq,
        ticker_hints=hints,
    )

    after = collect_validation_substrate_snapshot(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )

    p32 = recommend_phase32_branch(
        before=before,
        after=after,
        raw_repair=raw_rep,
        silver_seam=silver_seam,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "before": before,
        "after": after,
        "raw_facts_gap_targets": raw_preflight,
        "raw_facts_backfill_repair": raw_rep,
        "gis_like_silver_seam_repair": silver_seam,
        "deterministic_empty_cik_issuer_repair": issuer_rep,
        "downstream_substrate_retry": downstream_retry,
        "phase32": p32,
    }
