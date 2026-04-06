"""Referee: kill / sandbox / candidate_recipe with explicit policy (Phase 14)."""

from __future__ import annotations

from typing import Any

from research_engine.reviewers import LensResult


def latest_round_results(
    reviews: list[dict[str, Any]], *, round_number: int
) -> dict[str, str]:
    """Map lens -> decision for round."""
    m: dict[str, str] = {}
    for r in reviews:
        if int(r.get("round_number") or 0) != round_number:
            continue
        lens = str(r.get("reviewer_lens") or "")
        m[lens] = str(r.get("decision") or "")
    return m


def decide_referee(
    *,
    reviews: list[dict[str, Any]],
    quality_context: dict[str, Any],
    max_round: int = 2,
) -> dict[str, Any]:
    """
    Uses the highest completed round present in reviews (<= max_round).
    Policy mirrors workorder §9 + thin_input candidate_recipe ban.
    """
    qc, ins_frac = _qc_tuple(quality_context)
    round_use = max(
        (int(r.get("round_number") or 0) for r in reviews),
        default=0,
    )
    if round_use < 1:
        round_use = 1
    round_use = min(round_use, max_round)
    by_lens = latest_round_results(reviews, round_number=round_use)

    required = ("mechanism", "pit_data", "residual")
    objections: list[str] = []
    for lens in required:
        d = by_lens.get(lens, "concern")
        if d == "reject":
            objections.append(f"{lens}_reject")
        lr = next(
            (
                str(r.get("strongest_objection") or "")
                for r in reviews
                if int(r.get("round_number") or 0) == round_use
                and str(r.get("reviewer_lens") or "") == lens
            ),
            "",
        )
        if lr:
            objections.append(lr)

    disagreement = {
        "round_used": round_use,
        "per_lens_decision": dict(by_lens),
        "unresolved_objections": [o for o in objections if o],
        "quality_class_at_referee": qc,
    }

    if by_lens.get("mechanism") == "reject" or by_lens.get("pit_data") == "reject":
        return _out(
            "kill",
            "Required lens rejected (mechanism or PIT/data).",
            disagreement,
            {"action": "archive_hypothesis"},
        )
    if by_lens.get("residual") == "reject":
        return _out(
            "kill",
            "Residual lens rejected (fatal contradiction or missing grounding per policy).",
            disagreement,
            {"action": "archive_hypothesis"},
        )

    thin_only = qc == "thin_input" or ins_frac >= 0.75
    if thin_only:
        return _out(
            "sandbox",
            "thin_input substrate cannot justify candidate_recipe nomination alone (Phase 14 rule).",
            disagreement,
            {"action": "keep_in_registry", "note": "needs_thicker_public_evidence"},
        )

    strong_enough = qc in ("strong", "usable_with_gaps")
    any_concern = any(by_lens.get(l) == "concern" for l in required) or by_lens.get(
        "compression"
    ) == "concern"

    if strong_enough and not any_concern:
        return _out(
            "candidate_recipe",
            "No required rejects; quality context non-thin; proceeds to future validation track only (not product).",
            disagreement,
            {
                "action": "structured_validation_queue",
                "warning": "Does not mutate scoring or watchlist.",
            },
        )

    return _out(
        "sandbox",
        "Interesting but concerns remain or evidence not fully strong; disagreement preserved.",
        disagreement,
        {"action": "keep_in_registry"},
    )


def _qc_tuple(q: dict[str, Any]) -> tuple[str, float]:
    qc = str(q.get("quality_class") or "")
    if not qc and "metrics_json" in q:
        m = q.get("metrics_json") or {}
        ins_frac = float(m.get("insufficient_data_fraction") or 0.0)
        return "", ins_frac
    m = q.get("metrics_json") or {}
    ins_frac = float(m.get("insufficient_data_fraction") or 0.0)
    return qc, ins_frac


def _out(
    decision: str, rationale: str, disagreement: dict[str, Any], next_step: dict[str, Any]
) -> dict[str, Any]:
    return {
        "final_decision": decision,
        "rationale": rationale,
        "disagreement_json": disagreement,
        "next_step_json": next_step,
    }


def apply_lens_results_to_rows(
    hypothesis_id: str,
    round_number: int,
    results: list[LensResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lr in results:
        rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "reviewer_lens": lr.lens,
                "round_number": round_number,
                "decision": lr.decision,
                "strongest_objection": lr.strongest_objection,
                "evidence_needed": lr.evidence_needed,
                "proceed_to_validation": lr.proceed_to_validation,
                "review_json": {"detail": lr.detail_json},
            }
        )
    return rows
