"""Execute PIT specs per hypothesis family — dynamic spec_results, shared leakage rule."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from db import records as dbrec
from research_validation.metrics import norm_cik, norm_signal_date, state_change_rows_by_cik_sorted

from phase37.pit_experiment import fixture_join_key_mismatch_rows
from phase38.pit_join_logic import pick_state_change_at_or_before_signal, pit_safe_pick
from phase40.pit_engine import (
    STANDARD_BUCKETS,
    add_calendar_days,
    classify_row_outcome,
    count_joined_in_family,
    iso_date_prefix,
    rollup_standard,
)


def _load_governance_registry(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"lag_calendar_days": 14}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"lag_calendar_days": 14}


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


def run_phase40_pit_families(
    client: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    lag_calendar_days: int = 7,
    baseline_run_id: str | None = None,
    alternate_run_id: str | None = None,
    fixture_rows: list[dict[str, Any]] | None = None,
    governance_registry_path: str = "data/research_engine/governance_join_policy_registry_v1.json",
) -> dict[str, Any]:
    """
    Run legacy pit_as_of_boundary (3 specs) + 4 Phase 39 families (1 spec each).
    Each family returns row_results with spec_results: { spec_key: cell }.
    """
    experiment_id = str(uuid4())
    rows_f = fixture_rows if fixture_rows is not None else fixture_join_key_mismatch_rows()

    recent = dbrec.fetch_state_change_runs_for_universe_recent(
        client, universe_name=universe_name, limit=15
    )
    completed = [r for r in recent if str(r.get("status") or "") == "completed"]

    def _rid(i: int) -> str | None:
        if i < len(completed):
            return str(completed[i].get("id") or "")
        return None

    base_id = (baseline_run_id or "").strip() or _rid(0)
    alt_id = (alternate_run_id or "").strip() or _rid(1)

    if not base_id:
        return {
            "ok": False,
            "error": "no_completed_state_change_run",
            "experiment_id": experiment_id,
            "universe_name": universe_name,
        }

    run_row = dbrec.fetch_state_change_run(client, run_id=base_id) or {}
    run_finished_ymd = iso_date_prefix(str(run_row.get("finished_at") or run_row.get("created_at") or ""))

    scores_base = dbrec.fetch_state_change_scores_for_run(
        client, run_id=base_id, limit=state_change_scores_limit
    )
    sc_base = state_change_rows_by_cik_sorted(scores_base)

    scores_alt: list[dict[str, Any]] = []
    sc_alt: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    alt_effective_id: str | None = None
    if alt_id and alt_id != base_id:
        scores_alt = dbrec.fetch_state_change_scores_for_run(
            client, run_id=alt_id, limit=state_change_scores_limit
        )
        sc_alt = state_change_rows_by_cik_sorted(scores_alt)
        alt_effective_id = alt_id
    else:
        alt_effective_id = None

    gov = _load_governance_registry(governance_registry_path)
    gov_lag = int(gov.get("lag_calendar_days") or 14)

    families_out: list[dict[str, Any]] = []

    # --- Family 1: pit_as_of_boundary (Phase 38 trio, dynamic keys) ---
    leak1: list[dict[str, Any]] = []
    row1: list[dict[str, Any]] = []
    for fr in rows_f:
        cik = norm_cik(fr.get("cik"))
        sig = norm_signal_date(fr.get("signal_available_date")) or ""
        sym = str(fr.get("symbol") or "")

        pb, rb = pick_state_change_at_or_before_signal(sc_base, cik=cik, signal_date=sig)
        cat_b, det_b = classify_row_outcome(pb, rb, signal_bound=sig)
        _leakage_note(leak1, symbol=sym, spec_key="baseline_production_equivalent", picked=pb, signal_bound=sig)

        if alt_effective_id:
            pa, ra = pick_state_change_at_or_before_signal(sc_alt, cik=cik, signal_date=sig)
            cat_a, det_a = classify_row_outcome(pa, ra, signal_bound=sig)
            _leakage_note(
                leak1, symbol=sym, spec_key="alternate_prior_completed_run", picked=pa, signal_bound=sig
            )
        else:
            pa, ra = None, "alternate_skipped"
            cat_a, det_a = "alternate_spec_not_executed", {"pick_reason": "alternate_spec_skipped_no_distinct_prior_run"}

        sig_lag = add_calendar_days(sig, lag_calendar_days)
        pl, rl = pick_state_change_at_or_before_signal(sc_base, cik=cik, signal_date=sig_lag)
        cat_l, det_l = classify_row_outcome(pl, rl, signal_bound=sig_lag)
        _leakage_note(leak1, symbol=sym, spec_key="lag_calendar_signal_bound", picked=pl, signal_bound=sig_lag)

        spec_results = {
            "baseline_production_equivalent": _cell(
                outcome_category=cat_b,
                pick_reason=rb,
                detail=det_b,
                run_id=base_id,
            ),
            "alternate_prior_completed_run": _cell(
                outcome_category=cat_a,
                pick_reason=ra if isinstance(ra, str) else str(ra),
                detail=det_a if isinstance(det_a, dict) else {"detail": det_a},
                run_id=alt_effective_id,
                extra={"skipped": alt_effective_id is None},
            ),
            "lag_calendar_signal_bound": _cell(
                outcome_category=cat_l,
                pick_reason=rl,
                detail=det_l,
                run_id=base_id,
                extra={
                    "effective_signal_bound": sig_lag,
                    "lag_calendar_days": lag_calendar_days,
                },
            ),
        }
        row1.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "fixture_residual_join_bucket": fr.get("residual_join_bucket"),
                "spec_results": spec_results,
            }
        )

    passed1 = len(leak1) == 0
    summary1 = {
        sk: rollup_standard({str(i): row["spec_results"][sk] for i, row in enumerate(row1)})
        for sk in (
            "baseline_production_equivalent",
            "alternate_prior_completed_run",
            "lag_calendar_signal_bound",
        )
    }
    families_out.append(
        {
            "family_id": "pit_as_of_boundary_v1",
            "hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1",
            "spec_keys_executed": list(summary1.keys()),
            "row_results": row1,
            "summary_counts_by_spec": summary1,
            "joined_any_row": count_joined_in_family(row1) > 0,
            "leakage_audit": {
                "passed": passed1,
                "violations": leak1,
                "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
            },
        }
    )

    # --- Helper for single-spec families on baseline grid ---
    def run_single_spec_family(
        *,
        family_id: str,
        hypothesis_id: str,
        spec_key: str,
        signal_bound_fn,
        description: str,
        extra_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        leak: list[dict[str, Any]] = []
        rows_out: list[dict[str, Any]] = []
        for fr in rows_f:
            cik = norm_cik(fr.get("cik"))
            sig = norm_signal_date(fr.get("signal_available_date")) or ""
            sym = str(fr.get("symbol") or "")
            bound, meta = signal_bound_fn(sig, sym, cik)
            p, rreason = pick_state_change_at_or_before_signal(sc_base, cik=cik, signal_date=bound)
            cat, det = classify_row_outcome(p, rreason, signal_bound=bound)
            _leakage_note(leak, symbol=sym, spec_key=spec_key, picked=p, signal_bound=bound)
            cell_extra = {"effective_signal_bound": bound, **(meta or {})}
            if extra_meta:
                cell_extra["spec_meta"] = extra_meta
            rows_out.append(
                {
                    "symbol": sym,
                    "cik": cik,
                    "signal_available_date": sig,
                    "fixture_residual_join_bucket": fr.get("residual_join_bucket"),
                    "spec_results": {
                        spec_key: _cell(
                            outcome_category=cat,
                            pick_reason=rreason,
                            detail=det,
                            run_id=base_id,
                            extra=cell_extra,
                        )
                    },
                }
            )
        summ = {spec_key: {b: 0 for b in STANDARD_BUCKETS}}
        for row in rows_out:
            cell = (row.get("spec_results") or {}).get(spec_key) or {}
            oc = str(cell.get("outcome_category") or "")
            if oc == "alternate_spec_not_executed":
                continue
            if oc in summ[spec_key]:
                summ[spec_key][oc] += 1

        return {
            "family_id": family_id,
            "hypothesis_id": hypothesis_id,
            "spec_keys_executed": [spec_key],
            "description": description,
            "row_results": rows_out,
            "summary_counts_by_spec": summ,
            "joined_any_row": count_joined_in_family(rows_out) > 0,
            "leakage_audit": {
                "passed": len(leak) == 0,
                "violations": leak,
                "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
            },
        }

    # publication cadence: min(signal, run_finished)
    def _bound_pub(sig: str, _sym: str, _cik: str) -> tuple[str, dict[str, Any]]:
        if run_finished_ymd and len(run_finished_ymd) >= 10:
            b = min(sig[:10], run_finished_ymd[:10])
        else:
            b = sig[:10]
        return b, {
            "run_finished_at_date": run_finished_ymd,
            "bound_rule": "min(signal_available_date, state_change_run_finished_at_date)",
        }

    families_out.append(
        run_single_spec_family(
            family_id="score_publication_cadence_v1",
            hypothesis_id="hyp_score_publication_cadence_run_grid_lag_v1",
            spec_key="run_completion_anchored_signal_bound",
            signal_bound_fn=_bound_pub,
            description="Cap evaluation date by run completion so scores are not treated as available before the run finished.",
        )
    )

    # filing boundary: proxy = signal (substrate note)
    def _bound_filing(sig: str, _sym: str, _cik: str) -> tuple[str, dict[str, Any]]:
        return sig[:10], {
            "filing_public_ts_proxy": "signal_available_date",
            "note": "EDGAR filing timestamps not in substrate; strict pick uses recipe signal date as documented proxy.",
        }

    families_out.append(
        run_single_spec_family(
            family_id="signal_filing_boundary_v1",
            hypothesis_id="hyp_signal_availability_filing_boundary_v1",
            spec_key="filing_public_ts_strict_pick",
            signal_bound_fn=_bound_filing,
            description="Strict PIT pick at proxy filing-public bound (signal_available_date when filing ts absent).",
        )
    )

    # governance: signal + registry lag days
    def _bound_gov(sig: str, _sym: str, _cik: str) -> tuple[str, dict[str, Any]]:
        b = add_calendar_days(sig, gov_lag)
        return b, {"governance_lag_calendar_days": gov_lag, "registry_policy": gov.get("policy_id")}

    families_out.append(
        run_single_spec_family(
            family_id="governance_join_policy_v1",
            hypothesis_id="hyp_governance_safe_alternate_join_policy_v1",
            spec_key="governance_registry_bound_pick",
            signal_bound_fn=_bound_gov,
            description="Governance registry: extended calendar lag for join evaluation bound.",
            extra_meta={"registry_path": governance_registry_path},
        )
    )

    # stratified fixture: same as baseline (fixture-only cohort explicit)
    def _bound_strat(sig: str, _sym: str, _cik: str) -> tuple[str, dict[str, Any]]:
        return sig[:10], {"stratum": "join_key_mismatch_fixture_only", "replay": "production_equivalent_pick"}

    families_out.append(
        run_single_spec_family(
            family_id="issuer_sector_reporting_cadence_v1",
            hypothesis_id="hyp_issuer_sector_reporting_cadence_v1",
            spec_key="stratified_fixture_only_replay",
            signal_bound_fn=_bound_strat,
            description="Replay production-equivalent pick on the 8-row fixture cohort only (stratified scope).",
        )
    )

    all_leak_ok = all(f["leakage_audit"]["passed"] for f in families_out)

    return {
        "ok": True,
        "experiment_id": experiment_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "fixture_row_count": len(rows_f),
        "state_change_scores_limit": state_change_scores_limit,
        "lag_calendar_days": lag_calendar_days,
        "runs_resolved": {
            "baseline_run_id": base_id,
            "alternate_run_id": alt_effective_id,
            "completed_runs_considered": len(completed),
        },
        "scores_loaded": {"baseline": len(scores_base), "alternate": len(scores_alt)},
        "families_executed": families_out,
        "families_executed_count": len(families_out),
        "implemented_family_spec_count": sum(len(f.get("spec_keys_executed") or []) for f in families_out),
        "all_families_leakage_passed": all_leak_ok,
        "dynamic_schema": {
            "row_shape": "spec_results: dict[spec_key, outcome_cell]",
            "standard_outcome_buckets": list(STANDARD_BUCKETS),
        },
    }
