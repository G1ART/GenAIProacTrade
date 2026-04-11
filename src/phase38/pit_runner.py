"""DB-bound PIT execution for fixture rows — baseline vs alternate run vs lag signal bound."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from db import records as dbrec
from research_validation.metrics import norm_cik, norm_signal_date, state_change_rows_by_cik_sorted

from phase37.pit_experiment import fixture_join_key_mismatch_rows
from phase38.pit_join_logic import pick_state_change_at_or_before_signal, pit_safe_pick
from phase40.pit_engine import add_calendar_days, classify_row_outcome as _classify_row_outcome


def _summarize_counts(rows: list[dict[str, Any]], key: str = "outcome_category") -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        c = str(r.get(key) or "")
        out[c] = out.get(c, 0) + 1
    return out


def run_db_bound_pit_for_join_mismatch_fixture(
    client: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    lag_calendar_days: int = 7,
    baseline_run_id: str | None = None,
    alternate_run_id: str | None = None,
    fixture_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Execute three specs on the 8-row (or provided) fixture:
    1. baseline — latest completed run (or baseline_run_id), pick at signal_available_date
    2. alternate — prior completed run (or alternate_run_id), same pick rule
    3. lag — baseline scores, signal bound = signal + lag_calendar_days (governance-safe later evaluation)
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

    specs_meta = [
        {
            "spec_key": "baseline_production_equivalent",
            "state_change_run_id": base_id,
            "signal_policy": "signal_available_date_strict",
            "description": "Same pick rule as Phase 36 residual audit: bisect_right on as_of grid vs signal date.",
        },
        {
            "spec_key": "alternate_prior_completed_run",
            "state_change_run_id": alt_effective_id,
            "signal_policy": "signal_available_date_strict",
            "description": (
                "Second-most-recent completed run for universe (if distinct from baseline); "
                "same pick rule — tests whether an older score grid changes join classification."
            ),
            "skipped_reason": (
                None
                if alt_effective_id
                else "single_completed_run_or_duplicate_id"
            ),
        },
        {
            "spec_key": "lag_calendar_signal_bound",
            "state_change_run_id": base_id,
            "signal_policy": f"signal_available_date_plus_{lag_calendar_days}_calendar_days",
            "description": (
                "Baseline run scores; evaluation uses signal + N calendar days as upper bound "
                "for as_of (simulates later join decision without using post-signal price data)."
            ),
        },
    ]

    row_results: list[dict[str, Any]] = []
    leakage_flags: list[dict[str, Any]] = []

    for fr in rows_f:
        cik = norm_cik(fr.get("cik"))
        sig = norm_signal_date(fr.get("signal_available_date")) or ""
        sym = str(fr.get("symbol") or "")

        # --- baseline ---
        pb, rb = pick_state_change_at_or_before_signal(
            sc_base, cik=cik, signal_date=sig
        )
        cat_b, det_b = _classify_row_outcome(pb, rb, signal_bound=sig)
        ok_b, _ = pit_safe_pick(pb, signal_bound=sig)
        if not ok_b and pb is not None:
            leakage_flags.append(
                {
                    "symbol": sym,
                    "spec": "baseline",
                    "picked_as_of": str(pb.get("as_of_date") or "")[:10],
                    "signal_bound": sig,
                }
            )

        # --- alternate ---
        if alt_effective_id:
            pa, ra = pick_state_change_at_or_before_signal(
                sc_alt, cik=cik, signal_date=sig
            )
            cat_a, det_a = _classify_row_outcome(pa, ra, signal_bound=sig)
            ok_a, _ = pit_safe_pick(pa, signal_bound=sig)
            if not ok_a and pa is not None:
                leakage_flags.append(
                    {
                        "symbol": sym,
                        "spec": "alternate_prior_run",
                        "picked_as_of": str(pa.get("as_of_date") or "")[:10],
                        "signal_bound": sig,
                    }
                )
        else:
            pa, ra = None, "alternate_skipped"
            cat_a, det_a = "alternate_spec_not_executed", {
                "pick_reason": "alternate_spec_skipped_no_distinct_prior_run",
            }

        # --- lag ---
        sig_lag = add_calendar_days(sig, lag_calendar_days)
        pl, rl = pick_state_change_at_or_before_signal(
            sc_base, cik=cik, signal_date=sig_lag
        )
        cat_l, det_l = _classify_row_outcome(pl, rl, signal_bound=sig_lag)
        ok_l, _ = pit_safe_pick(pl, signal_bound=sig_lag)
        if not ok_l and pl is not None:
            leakage_flags.append(
                {
                    "symbol": sym,
                    "spec": "lag",
                    "picked_as_of": str(pl.get("as_of_date") or "")[:10],
                    "signal_bound": sig_lag,
                }
            )

        row_results.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "fixture_residual_join_bucket": fr.get("residual_join_bucket"),
                "baseline": {
                    "outcome_category": cat_b,
                    "pick_reason": rb,
                    "detail": det_b,
                    "state_change_run_id": base_id,
                },
                "alternate_prior_run": {
                    "outcome_category": cat_a,
                    "pick_reason": ra,
                    "detail": det_a,
                    "state_change_run_id": alt_effective_id,
                },
                "lag_signal_bound": {
                    "outcome_category": cat_l,
                    "pick_reason": rl,
                    "detail": det_l,
                    "effective_signal_bound": sig_lag,
                    "lag_calendar_days": lag_calendar_days,
                    "state_change_run_id": base_id,
                },
            }
        )

    def _counts_for_spec(spec_key: str) -> dict[str, int]:
        col = (
            "baseline"
            if spec_key == "baseline"
            else "alternate_prior_run"
            if spec_key == "alternate"
            else "lag_signal_bound"
        )
        synthetic = []
        for r in row_results:
            sub = r.get(col) or {}
            synthetic.append({"outcome_category": sub.get("outcome_category")})
        return _summarize_counts(synthetic)

    leakage_audit_passed = len(leakage_flags) == 0

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
        "executed_specs": specs_meta,
        "row_results": row_results,
        "summary_counts": {
            "baseline": _counts_for_spec("baseline"),
            "alternate_prior_run": _counts_for_spec("alternate"),
            "lag_signal_bound": _counts_for_spec("lag"),
        },
        "leakage_audit": {
            "passed": leakage_audit_passed,
            "violations": leakage_flags,
            "rule": "Any picked row must have as_of_date <= signal_bound for that spec.",
        },
        "scores_loaded": {
            "baseline": len(scores_base),
            "alternate": len(scores_alt),
        },
    }
