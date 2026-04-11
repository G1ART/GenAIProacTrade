"""Phase 41 — rerun filing + sector families with falsifier-grade substrate (shared leakage rule)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from db import records as dbrec
from phase37.pit_experiment import fixture_join_key_mismatch_rows
from phase38.pit_join_logic import pick_state_change_at_or_before_signal, pit_safe_pick
from phase40.pit_engine import STANDARD_BUCKETS, classify_row_outcome, count_joined_in_family
from research_validation.metrics import norm_cik, norm_signal_date, state_change_rows_by_cik_sorted

from phase41.substrate_filing import classify_filing_substrate_row, summarize_filing_substrate
from phase41.substrate_sector import classify_sector_substrate_row, summarize_sector_substrate


def _leakage_note(
    leakage_flags: list[dict[str, Any]],
    *,
    symbol: str,
    spec_key: str,
    picked: dict[str, Any] | None,
    signal_bound: str,
) -> None:
    ok, _ = pit_safe_pick(picked, signal_bound=signal_bound)
    if not ok and picked is not None:
        leakage_flags.append(
            {
                "symbol": symbol,
                "spec_key": spec_key,
                "picked_as_of": str(picked.get("as_of_date") or "")[:10],
                "signal_bound": signal_bound[:10],
            }
        )


def _cell(
    *,
    outcome_category: str,
    pick_reason: str,
    detail: dict[str, Any],
    run_id: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "outcome_category": outcome_category,
        "pick_reason": pick_reason,
        "detail": detail,
        "state_change_run_id": run_id,
    }
    if extra:
        out.update(extra)
    return out


def _resolve_baseline_run_id(
    client: Any,
    *,
    universe_name: str,
    baseline_run_id: str | None,
) -> str | None:
    bid = (baseline_run_id or "").strip()
    if bid:
        return bid
    recent = dbrec.fetch_state_change_runs_for_universe_recent(
        client, universe_name=universe_name, limit=15
    )
    completed = [r for r in recent if str(r.get("status") or "") == "completed"]
    if not completed:
        return None
    return str(completed[0].get("id") or "") or None


def run_phase41_falsifier_pit(
    client: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    baseline_run_id: str | None = None,
    fixture_rows: list[dict[str, Any]] | None = None,
    filing_index_limit: int = 200,
) -> dict[str, Any]:
    """
    Execute `signal_filing_boundary_v1` + `issuer_sector_reporting_cadence_v1` only,
    using filing_index + market_metadata_latest substrate.
    """
    experiment_id = str(uuid4())
    rows_f = fixture_rows if fixture_rows is not None else fixture_join_key_mismatch_rows()

    base_id = _resolve_baseline_run_id(
        client, universe_name=universe_name, baseline_run_id=baseline_run_id
    )
    if not base_id:
        return {
            "ok": False,
            "error": "no_completed_state_change_run",
            "experiment_id": experiment_id,
            "universe_name": universe_name,
        }

    scores_base = dbrec.fetch_state_change_scores_for_run(
        client, run_id=base_id, limit=state_change_scores_limit
    )
    sc_base = state_change_rows_by_cik_sorted(scores_base)

    ciks = sorted({norm_cik(r.get("cik")) for r in rows_f})
    filings_by_cik: dict[str, list[dict[str, Any]]] = {}
    for cik in ciks:
        filings_by_cik[cik] = dbrec.fetch_filing_index_rows_for_cik(
            client, cik=cik, limit=filing_index_limit
        )

    symbols = [str(r.get("symbol") or "").upper().strip() for r in rows_f]
    meta_by_sym = dbrec.fetch_market_metadata_latest_rows_for_symbols(client, symbols)

    filing_substrate_rows: list[dict[str, Any]] = []
    leak_f: list[dict[str, Any]] = []
    rows_filing: list[dict[str, Any]] = []

    for fr in rows_f:
        cik = norm_cik(fr.get("cik"))
        sig = norm_signal_date(fr.get("signal_available_date")) or ""
        sym = str(fr.get("symbol") or "")
        sub = classify_filing_substrate_row(
            signal_available_date=sig,
            filing_index_rows=filings_by_cik.get(cik, []),
        )
        filing_substrate_rows.append({"symbol": sym, "cik": cik, **sub})
        bound = sub["effective_pick_bound_ymd"]
        p, rreason = pick_state_change_at_or_before_signal(sc_base, cik=cik, signal_date=bound)
        cat, det = classify_row_outcome(p, rreason, signal_bound=bound)
        _leakage_note(leak_f, symbol=sym, spec_key="filing_public_ts_strict_pick", picked=p, signal_bound=bound)
        cell_extra: dict[str, Any] = {
            "effective_signal_bound": bound,
            "filing_substrate_classification": sub["classification"],
            "filing_bound_source": sub["filing_bound_source"],
            "explicit_proxy": bool(sub.get("explicit_proxy")),
            "filing_accession_no": sub.get("accession_no"),
            "filing_form": sub.get("form"),
        }
        rows_filing.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "fixture_residual_join_bucket": fr.get("residual_join_bucket"),
                "spec_results": {
                    "filing_public_ts_strict_pick": _cell(
                        outcome_category=cat,
                        pick_reason=rreason,
                        detail=det,
                        run_id=base_id,
                        extra=cell_extra,
                    )
                },
            }
        )

    spec_f = "filing_public_ts_strict_pick"
    summ_f = {spec_f: {b: 0 for b in STANDARD_BUCKETS}}
    for row in rows_filing:
        cell = (row.get("spec_results") or {}).get(spec_f) or {}
        oc = str(cell.get("outcome_category") or "")
        if oc in summ_f[spec_f]:
            summ_f[spec_f][oc] += 1

    family_filing = {
        "family_id": "signal_filing_boundary_v1",
        "hypothesis_id": "hyp_signal_availability_filing_boundary_v1",
        "spec_keys_executed": [spec_f],
        "description": (
            "Strict PIT pick at filing-public bound from filing_index when available; "
            "otherwise explicit signal_available_date proxy (labeled)."
        ),
        "row_results": rows_filing,
        "summary_counts_by_spec": summ_f,
        "joined_any_row": count_joined_in_family(rows_filing) > 0,
        "leakage_audit": {
            "passed": len(leak_f) == 0,
            "violations": leak_f,
            "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
        },
        "falsifier_substrate_note": "phase41_filing_index_wired",
    }

    sector_substrate_rows: list[dict[str, Any]] = []
    leak_s: list[dict[str, Any]] = []
    rows_sector: list[dict[str, Any]] = []
    spec_s = "sector_stratified_signal_pick_v1"

    for fr in rows_f:
        cik = norm_cik(fr.get("cik"))
        sig = norm_signal_date(fr.get("signal_available_date")) or ""
        sym = str(fr.get("symbol") or "").upper().strip()
        meta_row = meta_by_sym.get(sym)
        sec_sub = classify_sector_substrate_row(symbol=sym, metadata_row=meta_row)
        sector_substrate_rows.append({"symbol": sym, "cik": cik, **sec_sub})
        bound = sig[:10]
        stratum = sec_sub.get("sector_label") or "unknown"
        p, rreason = pick_state_change_at_or_before_signal(sc_base, cik=cik, signal_date=bound)
        cat, det = classify_row_outcome(p, rreason, signal_bound=bound)
        _leakage_note(leak_s, symbol=sym, spec_key=spec_s, picked=p, signal_bound=bound)
        rows_sector.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "fixture_residual_join_bucket": fr.get("residual_join_bucket"),
                "spec_results": {
                    spec_s: _cell(
                        outcome_category=cat,
                        pick_reason=rreason,
                        detail=det,
                        run_id=base_id,
                        extra={
                            "effective_signal_bound": bound,
                            "sector_stratum": stratum,
                            "sector_substrate_classification": sec_sub["classification"],
                        },
                    )
                },
            }
        )

    summ_s = {spec_s: {b: 0 for b in STANDARD_BUCKETS}}
    stratum_counts: dict[str, dict[str, int]] = defaultdict(lambda: {b: 0 for b in STANDARD_BUCKETS})
    for row in rows_sector:
        cell = (row.get("spec_results") or {}).get(spec_s) or {}
        oc = str(cell.get("outcome_category") or "")
        st = str((cell.get("sector_stratum") or "unknown"))
        if oc in summ_s[spec_s]:
            summ_s[spec_s][oc] += 1
        if oc in stratum_counts[st]:
            stratum_counts[st][oc] += 1

    family_sector = {
        "family_id": "issuer_sector_reporting_cadence_v1",
        "hypothesis_id": "hyp_issuer_sector_reporting_cadence_v1",
        "spec_keys_executed": [spec_s],
        "description": (
            "Production-equivalent PIT pick per row with sector stratum from market_metadata_latest; "
            "unknown stratum when sector missing."
        ),
        "row_results": rows_sector,
        "summary_counts_by_spec": summ_s,
        "sector_stratum_outcome_counts": {k: dict(v) for k, v in stratum_counts.items()},
        "joined_any_row": count_joined_in_family(rows_sector) > 0,
        "leakage_audit": {
            "passed": len(leak_s) == 0,
            "violations": leak_s,
            "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
        },
        "falsifier_substrate_note": "phase41_sector_metadata_wired",
    }

    families = [family_filing, family_sector]
    all_leak_ok = all(f["leakage_audit"]["passed"] for f in families)

    return {
        "ok": True,
        "experiment_id": experiment_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "fixture_row_count": len(rows_f),
        "baseline_run_id": base_id,
        "state_change_scores_limit": state_change_scores_limit,
        "scores_loaded": {"baseline": len(scores_base)},
        "families_executed": families,
        "families_executed_count": len(families),
        "implemented_family_spec_count": 2,
        "all_families_leakage_passed": all_leak_ok,
        "filing_substrate": {
            "per_row": filing_substrate_rows,
            "summary": summarize_filing_substrate(filing_substrate_rows),
        },
        "sector_substrate": {
            "per_row": sector_substrate_rows,
            "summary": summarize_sector_substrate(sector_substrate_rows),
        },
    }
