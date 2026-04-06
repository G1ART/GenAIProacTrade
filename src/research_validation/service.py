"""Orchestration: load public panels, score, compare, persist Phase 15 rows."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from db import records as dbrec
from research_validation.constants import (
    BASELINE_NAIVE,
    BASELINE_SIZE,
    BASELINE_STATE_CHANGE,
    BEAT_BASELINE_EPS,
    EXCESS_FIELD,
    HORIZON,
    MIN_SAMPLE_ROWS,
    NAIVE_NULL_SPREAD,
    SURVIVAL_STATUSES,
)
from research_validation.metrics import (
    mcap_baseline_score,
    norm_signal_date,
    recipe_score_from_hypothesis,
    safe_float,
    size_tertile_labels,
    state_change_index,
    top_bottom_spread,
    year_bucket,
)
from research_validation.policy import decide_survival
from research_validation.scorecard import build_scorecard, render_scorecard_markdown


def _eligible_for_validation(
    hypothesis: dict[str, Any], reviews: list[dict[str, Any]]
) -> tuple[bool, str]:
    if not reviews:
        return False, "reviews_required"
    st = str(hypothesis.get("status") or "")
    if st not in ("candidate_recipe", "sandboxed"):
        return False, "status_must_be_candidate_recipe_or_sandboxed"
    return True, ""


def _spread_triplet(rows: list[dict[str, Any]]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    pr = [(r["recipe_score"], r["excess"]) for r in rows]
    ps = [(r["sc_score"], r["excess"]) for r in rows]
    pm = [(r["mcap_score"], r["excess"]) for r in rows]
    return top_bottom_spread(pr), top_bottom_spread(ps), top_bottom_spread(pm)


def _spread_for_slice(
    rows: list[dict[str, Any]], *, field: str, value: str
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    sub = [r for r in rows if r.get(field) == value]
    return _spread_triplet(sub)


def run_recipe_validation(
    client: Any,
    *,
    hypothesis_id: str,
    panel_limit: int = 6000,
) -> dict[str, Any]:
    h = dbrec.fetch_research_hypothesis(client, hypothesis_id=hypothesis_id)
    if not h:
        return {"ok": False, "error": "hypothesis_not_found"}
    reviews = dbrec.fetch_research_reviews_for_hypothesis(client, hypothesis_id=hypothesis_id)
    ok_elig, err_elig = _eligible_for_validation(h, reviews)
    if not ok_elig:
        return {"ok": False, "error": err_elig}

    prog = dbrec.fetch_research_program(client, program_id=str(h["program_id"]))
    if not prog:
        return {"ok": False, "error": "program_not_found"}

    universe = str(prog.get("universe_name") or "")
    qctx = prog.get("linked_quality_context_json") or {}
    program_qc = str(qctx.get("quality_class") or "unknown")
    quality_run_id = qctx.get("public_core_cycle_quality_run_id")
    qc_row: Optional[dict[str, Any]] = None
    if quality_run_id:
        qc_row = dbrec.fetch_public_core_cycle_quality_run_by_id(
            client, str(quality_run_id)
        )
    state_run_id: Optional[str] = None
    if qc_row and qc_row.get("state_change_run_id"):
        state_run_id = str(qc_row["state_change_run_id"])
    if not state_run_id:
        state_run_id = dbrec.fetch_latest_state_change_run_id(
            client, universe_name=universe
        )
    if not state_run_id:
        return {"ok": False, "error": "no_state_change_run_for_universe"}

    as_of = dbrec.fetch_max_as_of_universe(client, universe_name=universe)
    symbols: list[str] = []
    if as_of:
        symbols = dbrec.fetch_symbols_universe_as_of(
            client, universe_name=universe, as_of_date=as_of
        )
    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=int(panel_limit)
    )
    scores = dbrec.fetch_state_change_scores_for_run(
        client, run_id=state_run_id, limit=50000
    )
    sc_map = state_change_index(scores)

    fam_raw = (h.get("feature_definition_json") or {}).get("families")
    if isinstance(fam_raw, list):
        families = {str(x) for x in fam_raw}
    else:
        families = set()

    rows_data: list[dict[str, Any]] = []
    for p in panels:
        excess = safe_float(p.get(EXCESS_FIELD))
        if excess is None:
            continue
        sig = norm_signal_date(p.get("signal_available_date"))
        cik = str(p.get("cik") or "").strip()
        if not cik or not sig:
            continue
        sc_row = sc_map.get((cik, sig))
        if not sc_row:
            continue
        sc_score = safe_float(sc_row.get("state_change_score_v1"))
        if sc_score is None:
            continue
        miss = int(sc_row.get("missing_component_count") or 0)
        liq = p.get("liquidity_proxy_json") or {}
        vol = safe_float(liq.get("avg_daily_volume")) if isinstance(liq, dict) else None
        mcap = safe_float(p.get("market_cap_asof"))
        rscore = recipe_score_from_hypothesis(
            families,
            state_change_score=sc_score,
            avg_daily_volume=vol,
            missing_component_count=miss,
        )
        rows_data.append(
            {
                "cik": cik,
                "symbol": str(p.get("symbol") or ""),
                "signal_date": sig,
                "excess": excess,
                "sc_score": sc_score,
                "recipe_score": rscore,
                "mcap": mcap,
                "mcap_score": mcap_baseline_score(mcap),
                "missing_comp": miss,
                "year": year_bucket(sig),
            }
        )

    if len(rows_data) < MIN_SAMPLE_ROWS:
        return {
            "ok": False,
            "error": "insufficient_joined_rows",
            "n_rows": len(rows_data),
            "min_required": MIN_SAMPLE_ROWS,
        }

    mcaps = [r["mcap"] for r in rows_data]
    for r, lbl in zip(rows_data, size_tertile_labels(mcaps)):
        r["size_cohort"] = lbl

    now = datetime.now(timezone.utc).isoformat()
    recipe_pooled, sc_pooled, mcap_pooled = _spread_triplet(rows_data)

    years = sorted({r["year"] for r in rows_data if r["year"] != "unknown_year"})
    yr_recipe: list[float] = []
    for y in years:
        rp, _, _ = _spread_for_slice(rows_data, field="year", value=y)
        if rp is not None:
            yr_recipe.append(rp)
    if len(yr_recipe) >= 2:
        mu = statistics.mean(yr_recipe)
        sd = statistics.pstdev(yr_recipe)
        window_stability_ratio = 1.0 - min(1.0, sd / (abs(mu) + 1e-6))
    else:
        window_stability_ratio = 0.45

    beats_naive = (
        recipe_pooled is not None
        and recipe_pooled > NAIVE_NULL_SPREAD + BEAT_BASELINE_EPS
    )
    beats_state_change = (
        recipe_pooled is not None
        and sc_pooled is not None
        and recipe_pooled > sc_pooled + BEAT_BASELINE_EPS
    )
    beats_size = (
        recipe_pooled is not None
        and mcap_pooled is not None
        and recipe_pooled > mcap_pooled + BEAT_BASELINE_EPS
    )

    links = dbrec.fetch_research_residual_links_for_hypothesis(
        client, hypothesis_id=hypothesis_id
    )
    contradiction_residual_count = sum(
        1
        for L in links
        if str(L.get("residual_triage_bucket") or "")
        == "contradictory_public_signal"
    )

    thin_input_heavy = program_qc == "thin_input"
    failed_degraded_emphasis = program_qc in ("failed", "degraded")

    survival = decide_survival(
        hypothesis_status=str(h.get("status") or ""),
        program_quality_class=program_qc,
        recipe_spread_pooled=recipe_pooled,
        sc_spread_pooled=sc_pooled,
        mcap_spread_pooled=mcap_pooled,
        beats_state_change=bool(beats_state_change),
        beats_naive=bool(beats_naive),
        beats_size=bool(beats_size),
        window_stability_ratio=float(window_stability_ratio),
        contradiction_residual_count=contradiction_residual_count,
        thin_input_heavy=thin_input_heavy,
        failed_degraded_emphasis=failed_degraded_emphasis,
    )

    if survival["survival_status"] not in SURVIVAL_STATUSES:
        return {"ok": False, "error": "invalid_survival_status"}

    baseline_config = {
        "baselines": [BASELINE_STATE_CHANGE, BASELINE_NAIVE, BASELINE_SIZE],
        "horizon": HORIZON,
        "excess_field": EXCESS_FIELD,
    }
    cohort_config = {
        "dimensions": ["program_quality_context", "size_tertile", "calendar_year"],
        "program_quality_class": program_qc,
    }
    window_config = {
        "calendar_years_present": years,
        "stability_metric": "rolling_year_recipe_spread_cv_proxy",
    }
    quality_filter = {
        "require_non_null_excess_next_quarter": True,
        "require_state_change_join_on_signal_date": True,
        "min_rows": MIN_SAMPLE_ROWS,
    }

    run_row = {
        "program_id": str(h["program_id"]),
        "hypothesis_id": hypothesis_id,
        "recipe_candidate_status_at_start": str(h.get("status") or ""),
        "baseline_config_json": baseline_config,
        "cohort_config_json": cohort_config,
        "window_config_json": window_config,
        "quality_filter_json": quality_filter,
        "linked_state_change_run_id": state_run_id,
        "linked_public_core_quality_run_id": str(quality_run_id) if quality_run_id else None,
        "status": "running",
        "created_at": now,
    }
    run_id = dbrec.insert_recipe_validation_run(client, run_row)

    result_rows: list[dict[str, Any]] = []
    result_rows.append(
        {
            "validation_run_id": run_id,
            "metric_name": "top_bottom_spread_excess",
            "metric_value": recipe_pooled,
            "cohort_key": "pooled",
            "baseline_name": "recipe",
            "result_json": {"n": len(rows_data)},
            "created_at": now,
        }
    )
    result_rows.append(
        {
            "validation_run_id": run_id,
            "metric_name": "top_bottom_spread_excess",
            "metric_value": sc_pooled,
            "cohort_key": "pooled",
            "baseline_name": BASELINE_STATE_CHANGE,
            "result_json": {"n": len(rows_data)},
            "created_at": now,
        }
    )
    result_rows.append(
        {
            "validation_run_id": run_id,
            "metric_name": "top_bottom_spread_excess",
            "metric_value": mcap_pooled,
            "cohort_key": "pooled",
            "baseline_name": BASELINE_SIZE,
            "result_json": {"n": len(rows_data)},
            "created_at": now,
        }
    )

    for y in years:
        rp, sp, mp = _spread_for_slice(rows_data, field="year", value=y)
        result_rows.append(
            {
                "validation_run_id": run_id,
                "metric_name": "top_bottom_spread_excess",
                "metric_value": rp,
                "cohort_key": f"year:{y}",
                "baseline_name": "recipe",
                "result_json": {},
                "created_at": now,
            }
        )
        result_rows.append(
            {
                "validation_run_id": run_id,
                "metric_name": "top_bottom_spread_excess",
                "metric_value": sp,
                "cohort_key": f"year:{y}",
                "baseline_name": BASELINE_STATE_CHANGE,
                "result_json": {},
                "created_at": now,
            }
        )

    for sz in ("size_small", "size_mid", "size_large"):
        rp, sp, _ = _spread_for_slice(rows_data, field="size_cohort", value=sz)
        result_rows.append(
            {
                "validation_run_id": run_id,
                "metric_name": "top_bottom_spread_excess",
                "metric_value": rp,
                "cohort_key": f"size:{sz}",
                "baseline_name": "recipe",
                "result_json": {},
                "created_at": now,
            }
        )
        result_rows.append(
            {
                "validation_run_id": run_id,
                "metric_name": "top_bottom_spread_excess",
                "metric_value": sp,
                "cohort_key": f"size:{sz}",
                "baseline_name": BASELINE_STATE_CHANGE,
                "result_json": {},
                "created_at": now,
            }
        )

    dbrec.insert_recipe_validation_results_batch(client, result_rows)

    def _delta(recipe: Optional[float], base: Optional[float]) -> dict[str, Any]:
        if recipe is None or base is None:
            return {"recipe": recipe, "baseline": base, "delta": None}
        return {"recipe": recipe, "baseline": base, "delta": recipe - base}

    comp_rows = [
        {
            "validation_run_id": run_id,
            "comparison_type": "spread_vs_baseline",
            "baseline_name": BASELINE_STATE_CHANGE,
            "candidate_delta_json": _delta(recipe_pooled, sc_pooled),
            "interpretation_json": {
                "beats": bool(beats_state_change),
                "eps": BEAT_BASELINE_EPS,
            },
            "created_at": now,
        },
        {
            "validation_run_id": run_id,
            "comparison_type": "spread_vs_baseline",
            "baseline_name": BASELINE_NAIVE,
            "candidate_delta_json": _delta(recipe_pooled, NAIVE_NULL_SPREAD),
            "interpretation_json": {"beats": bool(beats_naive)},
            "created_at": now,
        },
        {
            "validation_run_id": run_id,
            "comparison_type": "spread_vs_baseline",
            "baseline_name": BASELINE_SIZE,
            "candidate_delta_json": _delta(recipe_pooled, mcap_pooled),
            "interpretation_json": {"beats": bool(beats_size)},
            "created_at": now,
        },
    ]
    dbrec.insert_recipe_validation_comparisons_batch(client, comp_rows)

    dbrec.insert_recipe_survival_decision(
        client,
        {
            "validation_run_id": run_id,
            "hypothesis_id": hypothesis_id,
            "survival_status": survival["survival_status"],
            "rationale": survival["rationale"],
            "fragility_json": survival["fragility_json"],
            "next_step_json": survival["next_step_json"],
            "created_at": now,
        },
    )

    failures: list[dict[str, Any]] = []
    for sz in ("size_small", "size_mid", "size_large"):
        rp, sp, _ = _spread_for_slice(rows_data, field="size_cohort", value=sz)
        if rp is not None and sp is not None and rp + BEAT_BASELINE_EPS < sp:
            failures.append(
                {
                    "validation_run_id": run_id,
                    "hypothesis_id": hypothesis_id,
                    "residual_link_id": None,
                    "failure_reason": "recipe_underperforms_state_change_in_cohort",
                    "representative_context_json": {
                        "cohort": f"size:{sz}",
                        "recipe_spread": rp,
                        "state_change_spread": sp,
                    },
                    "premium_overlay_hint": "",
                    "created_at": now,
                }
            )

    for L in links:
        if str(L.get("residual_triage_bucket") or "") == "contradictory_public_signal":
            failures.append(
                {
                    "validation_run_id": run_id,
                    "hypothesis_id": hypothesis_id,
                    "residual_link_id": str(L.get("id")) if L.get("id") else None,
                    "failure_reason": "contradictory_residual_link",
                    "representative_context_json": {
                        "bucket": L.get("residual_triage_bucket"),
                        "unresolved_reason": L.get("unresolved_reason"),
                    },
                    "premium_overlay_hint": (L.get("premium_overlay_hint") or "")[:500],
                    "created_at": now,
                }
            )

    if program_qc == "thin_input":
        failures.append(
            {
                "validation_run_id": run_id,
                "hypothesis_id": hypothesis_id,
                "residual_link_id": None,
                "failure_reason": "thin_input_program_context_dependence",
                "representative_context_json": {"quality_class": program_qc},
                "premium_overlay_hint": "deeper_public_backfill_or_targeted_premium_later",
                "created_at": now,
            }
        )

    dbrec.insert_recipe_failure_cases_batch(client, failures)

    dbrec.update_recipe_validation_run(
        client,
        run_id=run_id,
        patch={"status": "completed", "error_message": None},
    )

    best_cohort, worst_cohort = _best_worst_cohort(result_rows)
    summary = {
        "strongest_positive": f"recipe_pooled_spread={recipe_pooled}",
        "strongest_fragility": f"window_stability_ratio={window_stability_ratio:.4f}",
        "best_cohort": best_cohort,
        "worst_cohort": worst_cohort,
        "residual_contradiction_count": contradiction_residual_count,
    }

    return {
        "ok": True,
        "validation_run_id": run_id,
        "survival": survival,
        "summary": summary,
        "n_rows": len(rows_data),
    }


def _best_worst_cohort(result_rows: list[dict[str, Any]]) -> tuple[str, str]:
    best = ("", float("-inf"))
    worst = ("", float("inf"))
    for row in result_rows:
        if str(row.get("baseline_name")) != "recipe":
            continue
        if row.get("metric_name") != "top_bottom_spread_excess":
            continue
        v = row.get("metric_value")
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        ck = str(row.get("cohort_key") or "")
        if fv > best[1]:
            best = (ck, fv)
        if fv < worst[1]:
            worst = (ck, fv)
    return best[0] or "n/a", worst[0] or "n/a"


def export_scorecard_for_hypothesis(
    client: Any,
    *,
    hypothesis_id: str,
    validation_run_id: Optional[str] = None,
) -> dict[str, Any]:
    h = dbrec.fetch_research_hypothesis(client, hypothesis_id=hypothesis_id)
    if not h:
        return {"ok": False, "error": "hypothesis_not_found"}
    prog = dbrec.fetch_research_program(client, program_id=str(h["program_id"]))
    if not prog:
        return {"ok": False, "error": "program_not_found"}

    run: Optional[dict[str, Any]] = None
    if validation_run_id:
        run = dbrec.fetch_recipe_validation_run(client, run_id=validation_run_id)
        if not run or str(run.get("hypothesis_id")) != hypothesis_id:
            return {"ok": False, "error": "validation_run_not_found_or_mismatch"}
    else:
        run = dbrec.fetch_latest_recipe_validation_run_for_hypothesis(
            client, hypothesis_id=hypothesis_id, status="completed"
        )
        if not run:
            return {"ok": False, "error": "no_completed_validation_run"}

    rid = str(run["id"])
    comps = dbrec.fetch_recipe_validation_comparisons_for_run(client, validation_run_id=rid)
    survival = dbrec.fetch_recipe_survival_for_run(client, validation_run_id=rid)
    failures = dbrec.fetch_recipe_failure_cases_for_run(client, validation_run_id=rid)
    results = dbrec.fetch_recipe_validation_results_for_run(client, validation_run_id=rid)
    if not survival:
        return {"ok": False, "error": "survival_row_missing"}

    best_cohort, worst_cohort = _best_worst_cohort(results)
    contradiction_count = sum(
        1
        for f in failures
        if f.get("failure_reason") == "contradictory_residual_link"
    )
    summary = {
        "strongest_positive": f"pooled_spread_from_results",
        "strongest_fragility": survival.get("fragility_json"),
        "best_cohort": best_cohort,
        "worst_cohort": worst_cohort,
        "residual_contradiction_count": contradiction_count,
    }
    card = build_scorecard(
        hypothesis=h,
        program=prog,
        validation_run=run,
        comparisons=comps,
        survival=survival,
        failure_cases=failures,
        summary=summary,
    )
    return {
        "ok": True,
        "scorecard": card,
        "markdown": render_scorecard_markdown(card),
        "validation_run_id": rid,
    }


def report_validation_run_bundle(client: Any, *, validation_run_id: str) -> dict[str, Any]:
    run = dbrec.fetch_recipe_validation_run(client, run_id=validation_run_id)
    if not run:
        return {"ok": False, "error": "run_not_found"}
    rid = str(run["id"])
    return {
        "ok": True,
        "run": run,
        "results": dbrec.fetch_recipe_validation_results_for_run(
            client, validation_run_id=rid
        ),
        "comparisons": dbrec.fetch_recipe_validation_comparisons_for_run(
            client, validation_run_id=rid
        ),
        "survival": dbrec.fetch_recipe_survival_for_run(client, validation_run_id=rid),
        "failures": dbrec.fetch_recipe_failure_cases_for_run(
            client, validation_run_id=rid
        ),
    }


def compare_baselines_for_hypothesis(client: Any, *, hypothesis_id: str) -> dict[str, Any]:
    run = dbrec.fetch_latest_recipe_validation_run_for_hypothesis(
        client, hypothesis_id=hypothesis_id, status="completed"
    )
    if not run:
        return {"ok": False, "error": "no_completed_validation_run"}
    rid = str(run["id"])
    comps = dbrec.fetch_recipe_validation_comparisons_for_run(client, validation_run_id=rid)
    return {"ok": True, "validation_run_id": rid, "comparisons": comps}
