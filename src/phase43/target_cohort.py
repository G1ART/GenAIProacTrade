"""Load Phase 43 work set from Phase 42 Supabase-fresh bundle (cohort-locked)."""

from __future__ import annotations

from typing import Any

from phase43.target_types import CohortTargetRow

EXACT_COHORT_SIZE = 8


def load_targets_from_phase42_supabase_bundle(bundle: dict[str, Any]) -> list[CohortTargetRow]:
    """
    `row_level_blockers` must be exactly 8 rows, `blocker_replay_source` expected `supabase_fresh`
    for authoritative closeout input (not enforced here — orchestrator may warn).
    """
    rows = bundle.get("row_level_blockers") or []
    if len(rows) != EXACT_COHORT_SIZE:
        raise ValueError(
            f"phase43 cohort lock: expected {EXACT_COHORT_SIZE} row_level_blockers, got {len(rows)}"
        )
    seen: set[tuple[str, str]] = set()
    out: list[CohortTargetRow] = []
    for r in rows:
        sym = str(r.get("symbol") or "").upper().strip()
        cik = str(r.get("cik") or "").strip()
        key = (sym, cik)
        if key in seen:
            raise ValueError(f"duplicate cohort row: {sym} {cik}")
        seen.add(key)
        out.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": str(r.get("signal_available_date") or "")[:10],
                "filing_blocker_cause_before": str(r.get("filing_blocker_cause") or ""),
                "sector_blocker_cause_before": str(r.get("sector_blocker_cause") or ""),
            }
        )
    return out


def merge_fixture_residual_from_phase41_bundle(
    targets: list[CohortTargetRow],
    phase41_bundle: dict[str, Any],
) -> list[CohortTargetRow]:
    by_sym: dict[str, str] = {}
    pit = phase41_bundle.get("pit_execution") or {}
    for f in pit.get("families_executed") or []:
        if str(f.get("family_id") or "") != "signal_filing_boundary_v1":
            continue
        for row in f.get("row_results") or []:
            s = str(row.get("symbol") or "").upper().strip()
            b = str(row.get("fixture_residual_join_bucket") or "")
            if s:
                by_sym[s] = b
    for t in targets:
        sym = str(t.get("symbol") or "").upper().strip()
        t["residual_join_bucket"] = by_sym.get(
            sym, "state_change_built_but_join_key_mismatch"
        )
    return targets
