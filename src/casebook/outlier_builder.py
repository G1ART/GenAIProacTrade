"""First-pass heuristic outlier detection from Phase 4–7 layers (marked is_heuristic)."""

from __future__ import annotations

from typing import Any, Optional

from message_contract import OVERLAY_FUTURE_SEAMS_DEFAULT

DETECTION_LOGIC_VERSION = "outlier_heuristic_v1"

# Tunables (documented in README Phase 8)
STRONG_SCORE_ABS = 1.0
WEAK_REACTION_THRESHOLD = 0.01
MISSING_COMPONENTS_HEAVY = 2


def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _avg_field(rows: list[dict[str, Any]], key: str) -> Optional[float]:
    vals = [_f(r.get(key)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _payload_from_harness_row(row: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not row:
        return {}
    pj = row.get("payload_json")
    return pj if isinstance(pj, dict) else {}


def _memo_flags(memo: Optional[dict[str, Any]]) -> list[Any]:
    if not memo:
        return []
    fj = memo.get("referee_flags_json")
    if isinstance(fj, list):
        return fj
    return []


def _memo_json_blob(memo: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not memo:
        return {}
    mj = memo.get("memo_json")
    return mj if isinstance(mj, dict) else {}


def build_message_fields(
    *,
    short_title: str,
    why_matters: str,
    what_wrong: str,
    unknown: str,
    plain: str,
) -> dict[str, str]:
    return {
        "message_short_title": short_title[:500],
        "message_why_matters": why_matters[:4000],
        "message_what_could_wrong": what_wrong[:4000],
        "message_unknown": unknown[:4000],
        "message_plain_language": plain[:4000],
    }


def detect_outliers_for_candidate(
    *,
    candidate: dict[str, Any],
    score: Optional[dict[str, Any]],
    validation_panel: Optional[dict[str, Any]],
    forward_row: Optional[dict[str, Any]],
    memo: Optional[dict[str, Any]],
    harness_row: Optional[dict[str, Any]],
    components: list[dict[str, Any]],
    company_name: str,
) -> list[dict[str, Any]]:
    """
    Returns list of entry dicts (no id/casebook_run_id) ready for DB insert.
    Multiple outlier_type rows per candidate allowed.
    """
    cid = str(candidate.get("id") or "")
    cik = str(candidate.get("cik") or "")
    ticker = str(candidate.get("ticker") or "").strip() or None
    as_of = str(candidate.get("as_of_date") or "")
    cc = str(candidate.get("candidate_class") or "")
    issuer_id = candidate.get("issuer_id")
    memo_id = str(memo["id"]) if memo and memo.get("id") is not None else None

    sc = _f(score.get("state_change_score_v1")) if score else None
    direction = str(score.get("state_change_direction") or "unknown") if score else "unknown"
    miss_comp = int(score.get("missing_component_count") or 0) if score else 0
    gating = str(score.get("gating_status") or "") if score else ""

    payload = _payload_from_harness_row(harness_row)
    miss_ind = payload.get("missing_data_indicators") or []
    if not isinstance(miss_ind, list):
        miss_ind = []

    base_trace: dict[str, Any] = {
        "detection_logic_version": DETECTION_LOGIC_VERSION,
        "candidate_id": cid,
        "cik": cik,
        "as_of_date": as_of,
        "state_change_score": sc,
        "candidate_class": cc,
    }

    lim_parts = [
        "Heuristic v1: not predictive validation; research joins may misalign dates.",
    ]
    if miss_comp >= MISSING_COMPONENTS_HEAVY:
        lim_parts.append(f"missing_component_count={miss_comp}.")
    if miss_ind:
        lim_parts.append("Harness missing_data_indicators present.")
    limitation_notes = " ".join(lim_parts)

    contam_json: dict[str, Any] = {
        "missing_data_indicators": miss_ind,
        "missing_component_count": miss_comp,
        "gating_status": gating,
    }

    entries: list[dict[str, Any]] = []

    excess_1m = _f(validation_panel.get("excess_return_1m")) if validation_panel else None
    raw_1m = _f(validation_panel.get("raw_return_1m")) if validation_panel else None
    sig_avail = validation_panel.get("signal_available_date") if validation_panel else None

    fwd_excess = _f(forward_row.get("excess_forward_return")) if forward_row else None
    fwd_raw = _f(forward_row.get("raw_forward_return")) if forward_row else None
    reaction_excess = excess_1m if excess_1m is not None else fwd_excess
    reaction_raw = raw_1m if raw_1m is not None else fwd_raw

    # --- reaction_gap ---
    if sc is not None and abs(sc) >= STRONG_SCORE_ABS and cc in (
        "investigate_now",
        "investigate_watch",
    ):
        if reaction_excess is not None:
            contrary = False
            if direction in ("increase", "up", "positive") and reaction_excess < -WEAK_REACTION_THRESHOLD:
                contrary = True
            if direction in ("decrease", "down", "negative") and reaction_excess > WEAK_REACTION_THRESHOLD:
                contrary = True
            if contrary:
                msg = build_message_fields(
                    short_title=f"Reaction gap: {ticker or cik} ({as_of})",
                    why_matters="Deterministic state-change signal was elevated while joined post-signal excess return moved the other way — worth documenting, not forecasting.",
                    what_wrong="Stale filing alignment, wrong horizon, liquidity noise, or the signal not being price-relevant.",
                    unknown="Whether the gap persists beyond the joined horizon; macro shocks not modeled here.",
                    plain=f"{ticker or cik} on {as_of}: state-change direction {direction} with score {sc}, "
                    f"but excess return (panel or forward join) was {reaction_excess}. "
                    "This is a discrepancy snapshot, not a recommendation.",
                )
                entries.append(
                    {
                        "candidate_id": cid,
                        "issuer_id": issuer_id,
                        "cik": cik,
                        "ticker": ticker,
                        "company_name": company_name,
                        "as_of_date": as_of,
                        "memo_id": memo_id,
                        "outlier_type": "reaction_gap",
                        "outlier_severity": min(100.0, abs(sc) * 20 + abs(reaction_excess) * 200),
                        "primary_discrepancy_summary": (
                            f"State-change signal ({direction}, score={sc}) vs excess return {reaction_excess} "
                            f"(1m-class join; panel_date_hint={sig_avail})."
                        ),
                        "expected_pattern_summary": (
                            "Naive expectation from direction label alone would be qualitative alignment with "
                            "subsequent excess return; we do not assert probability."
                        ),
                        "observed_pattern_summary": (
                            f"Observed joined excess {reaction_excess}; raw {reaction_raw}."
                        ),
                        "uncertainty_summary": "Join is research alignment, not a controlled experiment; label leakage into features is avoided elsewhere but interpretation risk remains.",
                        "limitation_notes": limitation_notes,
                        "contamination_regime_missingness_json": {
                            **contam_json,
                            "validation_accession": validation_panel.get("accession_no")
                            if validation_panel
                            else None,
                            "forward_horizon": forward_row.get("horizon_type") if forward_row else None,
                        },
                        "source_trace": {
                            **base_trace,
                            "outlier_type": "reaction_gap",
                            "validation_panel_id": validation_panel.get("id")
                            if validation_panel
                            else None,
                            "forward_returns_row_id": forward_row.get("id") if forward_row else None,
                        },
                        "status": "open",
                        "is_heuristic": True,
                        "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                        **msg,
                    }
                )

    # --- thesis_challenge_divergence ---
    flags = _memo_flags(memo)
    mj = _memo_json_blob(memo)
    ref_passed = memo.get("referee_passed") if memo is not None else True
    if memo is not None and (ref_passed is False or len(flags) > 0):
        codes = [str(f.get("code")) for f in flags if isinstance(f, dict)]
        msg = build_message_fields(
            short_title=f"Memo/referee tension: {ticker or cik} ({as_of})",
            why_matters="Investigation memo or referee flagged structural concerns despite candidate visibility — operator should reconcile.",
            what_wrong="Referee false positive, thin data, or genuine model-doc tension.",
            unknown="Whether issues persist after data refresh.",
            plain=f"{ticker or cik}: referee_passed={ref_passed}; flags={','.join(codes[:6]) or 'none'}.",
        )
        entries.append(
            {
                "candidate_id": cid,
                "issuer_id": issuer_id,
                "cik": cik,
                "ticker": ticker,
                "company_name": company_name,
                "as_of_date": as_of,
                "memo_id": memo_id,
                "outlier_type": "thesis_challenge_divergence",
                "outlier_severity": 50.0 + min(40.0, float(len(flags) * 10)),
                "primary_discrepancy_summary": (
                    f"Memo/referee state: passed={ref_passed}, flag_count={len(flags)}."
                ),
                "expected_pattern_summary": "Clean memo with no referee flags when deterministic signal is showcased.",
                "observed_pattern_summary": f"Referee flags: {codes[:8]}",
                "uncertainty_summary": "Referee is rule-based; does not judge economic truth.",
                "limitation_notes": limitation_notes,
                "contamination_regime_missingness_json": contam_json,
                "source_trace": {**base_trace, "outlier_type": "thesis_challenge_divergence", "memo_id": memo_id},
                "status": "open",
                "is_heuristic": True,
                "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                **msg,
            }
        )

    # --- contamination_override ---
    if miss_comp >= MISSING_COMPONENTS_HEAVY or len(miss_ind) >= 2 or gating != "ok":
        if cc in ("investigate_now", "investigate_watch"):
            msg = build_message_fields(
                short_title=f"Data stress on flagged candidate: {ticker or cik}",
                why_matters="High missingness or non-ok gating on a visible candidate — track explicitly.",
                what_wrong="Signal may be artifact of sparse components.",
                unknown="Whether additional filings improve coverage.",
                plain=f"{ticker or cik}: missing_components={miss_comp}, gating={gating}, "
                f"missing_indicators_n={len(miss_ind)}.",
            )
            entries.append(
                {
                    "candidate_id": cid,
                    "issuer_id": issuer_id,
                    "cik": cik,
                    "ticker": ticker,
                    "company_name": company_name,
                    "as_of_date": as_of,
                    "memo_id": memo_id,
                    "outlier_type": "contamination_override",
                    "outlier_severity": 40.0 + float(miss_comp) * 10,
                    "primary_discrepancy_summary": (
                        f"Promoted candidate class {cc} with missing_components={miss_comp}, gating={gating}."
                    ),
                    "expected_pattern_summary": "Investigate_now/watch usually implies ok gating and light missingness.",
                    "observed_pattern_summary": f"miss_ind sample: {miss_ind[:5]}",
                    "uncertainty_summary": "Heuristic severity; does not impute false data.",
                    "limitation_notes": limitation_notes,
                    "contamination_regime_missingness_json": contam_json,
                    "source_trace": {**base_trace, "outlier_type": "contamination_override"},
                    "status": "open",
                    "is_heuristic": True,
                    "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                    **msg,
                }
            )

    # --- regime_mismatch ---
    rf = _avg_field(components, "regime_fit_score")
    if rf is not None and rf < 0.35 and sc is not None and abs(sc) >= 0.8:
        msg = build_message_fields(
            short_title=f"Regime fit weak vs score: {ticker or cik}",
            why_matters="Components average low regime_fit_score while headline score is non-trivial.",
            what_wrong="Regime mis-tag or genuine mismatch.",
            unknown="Whether regime scores are null-heavy.",
            plain=f"{ticker or cik}: avg regime_fit_score≈{rf:.3f}, state_change_score={sc}.",
        )
        entries.append(
            {
                "candidate_id": cid,
                "issuer_id": issuer_id,
                "cik": cik,
                "ticker": ticker,
                "company_name": company_name,
                "as_of_date": as_of,
                "memo_id": memo_id,
                "outlier_type": "regime_mismatch",
                "outlier_severity": 55.0,
                "primary_discrepancy_summary": f"Average regime_fit_score {rf} vs score {sc}.",
                "expected_pattern_summary": "Higher regime fit when headline score is strong.",
                "observed_pattern_summary": f"Components counted: {len(components)}.",
                "uncertainty_summary": "regime_fit may be sparsely populated per signal row.",
                "limitation_notes": limitation_notes,
                "contamination_regime_missingness_json": {**contam_json, "avg_regime_fit_score": rf},
                "source_trace": {**base_trace, "outlier_type": "regime_mismatch"},
                "status": "open",
                "is_heuristic": True,
                "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                **msg,
            }
        )

    # --- persistence_failure ---
    vel = _avg_field(components, "velocity_score")
    per = _avg_field(components, "persistence_score")
    if (
        vel is not None
        and per is not None
        and vel > 0.45
        and per < 0.25
        and cc in ("investigate_now", "investigate_watch")
    ):
        msg = build_message_fields(
            short_title=f"Velocity vs persistence split: {ticker or cik}",
            why_matters="High velocity with low persistence suggests unstable driver pattern.",
            what_wrong="One-off shock vs recurring shift.",
            unknown="Horizon mismatch across components.",
            plain=f"{ticker or cik}: avg_velocity≈{vel:.3f}, avg_persistence≈{per:.3f}.",
        )
        entries.append(
            {
                "candidate_id": cid,
                "issuer_id": issuer_id,
                "cik": cik,
                "ticker": ticker,
                "company_name": company_name,
                "as_of_date": as_of,
                "memo_id": memo_id,
                "outlier_type": "persistence_failure",
                "outlier_severity": 48.0,
                "primary_discrepancy_summary": f"velocity_avg={vel}, persistence_avg={per}.",
                "expected_pattern_summary": "Velocity shifts backed by persistence when structural.",
                "observed_pattern_summary": "Velocity elevated, persistence weak (averages).",
                "uncertainty_summary": "Aggregates hide per-signal heterogeneity.",
                "limitation_notes": limitation_notes,
                "contamination_regime_missingness_json": {
                    **contam_json,
                    "avg_velocity_score": vel,
                    "avg_persistence_score": per,
                },
                "source_trace": {**base_trace, "outlier_type": "persistence_failure"},
                "status": "open",
                "is_heuristic": True,
                "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                **msg,
            }
        )

    # --- unexplained_residual ---
    if cc == "insufficient_data" and sc is not None and abs(sc) >= 0.6:
        msg = build_message_fields(
            short_title=f"Class/score tension: {ticker or cik}",
            why_matters="Marked insufficient_data but numeric score is not near neutral.",
            what_wrong="Classification threshold vs composite score misalignment.",
            unknown="Which sub-scores drove the split.",
            plain=f"{ticker or cik}: class={cc}, score={sc}.",
        )
        entries.append(
            {
                "candidate_id": cid,
                "issuer_id": issuer_id,
                "cik": cik,
                "ticker": ticker,
                "company_name": company_name,
                "as_of_date": as_of,
                "memo_id": memo_id,
                "outlier_type": "unexplained_residual",
                "outlier_severity": 35.0,
                "primary_discrepancy_summary": f"candidate_class {cc} vs |score|={abs(sc)}.",
                "expected_pattern_summary": "Low/ambiguous score when data insufficient.",
                "observed_pattern_summary": f"score={sc}",
                "uncertainty_summary": "May be intentional gating edge case.",
                "limitation_notes": limitation_notes,
                "contamination_regime_missingness_json": contam_json,
                "source_trace": {**base_trace, "outlier_type": "unexplained_residual"},
                "status": "open",
                "is_heuristic": True,
                "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                **msg,
            }
        )

    return entries
