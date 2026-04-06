"""Orchestration for research program CLI (Phase 14)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db import records as dbrec
from research_engine.constants import (
    DEFAULT_PHASE14_PROGRAM_TITLE,
    DEFAULT_PHASE14_RESEARCH_QUESTION,
    PHASE14_HORIZON,
    PHASE14_PREMIUM_ALLOWED,
)
from research_engine.dossier import build_dossier
from research_engine.forge import SEED_HYPOTHESES
from research_engine.referee import apply_lens_results_to_rows, decide_referee
from research_engine.reviewers import run_all_lenses_for_round


def create_program(
    client: Any,
    *,
    universe_name: str,
    title: Optional[str] = None,
    quality_run_id: Optional[str] = None,
    owner_actor: str = "operator",
) -> dict[str, Any]:
    qctx: dict[str, Any] = {}
    if quality_run_id:
        row = dbrec.fetch_public_core_cycle_quality_run_by_id(client, quality_run_id)
        if row:
            qctx = {
                "public_core_cycle_quality_run_id": quality_run_id,
                "quality_class": row.get("quality_class"),
                "metrics_json": row.get("metrics_json"),
                "gap_reasons_ranked": row.get("gap_reasons_ranked"),
                "residual_triage_json": row.get("residual_triage_json"),
            }
    else:
        recent = dbrec.fetch_public_core_cycle_quality_runs_recent(client, limit=1)
        if recent:
            r0 = recent[0]
            qctx = {
                "public_core_cycle_quality_run_id": r0.get("id"),
                "quality_class": r0.get("quality_class"),
                "metrics_json": r0.get("metrics_json"),
                "gap_reasons_ranked": r0.get("gap_reasons_ranked"),
                "residual_triage_json": r0.get("residual_triage_json"),
            }

    now = datetime.now(timezone.utc).isoformat()
    pid = dbrec.insert_research_program(
        client,
        {
            "title": title or DEFAULT_PHASE14_PROGRAM_TITLE,
            "research_question": DEFAULT_PHASE14_RESEARCH_QUESTION,
            "horizon_type": PHASE14_HORIZON,
            "universe_name": universe_name,
            "status": "active",
            "owner_actor": owner_actor,
            "program_constraints_json": {
                "phase": 14,
                "single_program_lock": True,
                "public_data_only": True,
            },
            "linked_quality_context_json": qctx,
            "premium_overlays_allowed": PHASE14_PREMIUM_ALLOWED,
            "created_at": now,
            "updated_at": now,
        },
    )
    return {"ok": True, "program_id": pid, "linked_quality_context_json": qctx}


def generate_hypotheses(client: Any, *, program_id: str) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found"}
    qctx = prog.get("linked_quality_context_json") or {}
    triage = qctx.get("residual_triage_json") or {}
    dominant = triage.get("dominant_bucket")
    unresolved = []
    recent_id = qctx.get("public_core_cycle_quality_run_id")
    if recent_id:
        full = dbrec.fetch_public_core_cycle_quality_run_by_id(client, str(recent_id))
        if full:
            unresolved = full.get("unresolved_residual_items") or []

    created: list[str] = []
    for seed in SEED_HYPOTHESES:
        now = datetime.now(timezone.utc).isoformat()
        hid = dbrec.insert_research_hypothesis_object(
            client,
            {
                "program_id": program_id,
                "hypothesis_title": seed["hypothesis_title"],
                "economic_rationale": seed["economic_rationale"],
                "mechanism_json": seed["mechanism_json"],
                "feature_definition_json": seed["feature_definition_json"],
                "scope_limits_json": seed["scope_limits_json"],
                "expected_effect_json": seed["expected_effect_json"],
                "failure_modes_json": seed["failure_modes_json"],
                "status": "proposed",
                "review_rounds_completed": 0,
                "created_at": now,
                "updated_at": now,
            },
        )
        created.append(hid)
        for item in unresolved[:5]:
            dbrec.insert_research_residual_link(
                client,
                {
                    "hypothesis_id": hid,
                    "outlier_casebook_entry_id": None,
                    "residual_triage_bucket": item.get("residual_bucket"),
                    "unresolved_reason": item.get("why_unresolved"),
                    "premium_overlay_hint": item.get("suggested_premium_overlay"),
                    "claims_to_explain": seed.get("claims_to_explain", ""),
                },
            )
        if not unresolved and dominant:
            dbrec.insert_research_residual_link(
                client,
                {
                    "hypothesis_id": hid,
                    "outlier_casebook_entry_id": None,
                    "residual_triage_bucket": dominant,
                    "unresolved_reason": str(triage.get("dominant_explanation") or ""),
                    "premium_overlay_hint": "",
                    "claims_to_explain": seed.get("claims_to_explain", ""),
                },
            )

    return {"ok": True, "hypothesis_ids": created, "dominant_residual_bucket": dominant}


def run_review_round(client: Any, *, hypothesis_id: str) -> dict[str, Any]:
    h = dbrec.fetch_research_hypothesis(client, hypothesis_id)
    if not h:
        return {"ok": False, "error": "hypothesis_not_found"}
    rounds_done = int(h.get("review_rounds_completed") or 0)
    if rounds_done >= 2:
        return {"ok": False, "error": "max_review_rounds_reached", "rounds_done": rounds_done}
    next_round = rounds_done + 1

    prog = dbrec.fetch_research_program(client, str(h["program_id"]))
    qctx = (prog or {}).get("linked_quality_context_json") or {}
    qctx_full = dict(qctx)
    if qctx.get("public_core_cycle_quality_run_id") and "metrics_json" not in qctx_full:
        row = dbrec.fetch_public_core_cycle_quality_run_by_id(
            client, str(qctx["public_core_cycle_quality_run_id"])
        )
        if row:
            qctx_full["quality_class"] = row.get("quality_class")
            qctx_full["metrics_json"] = row.get("metrics_json")

    links = dbrec.fetch_research_residual_links_for_hypothesis(client, hypothesis_id)
    triage = qctx.get("residual_triage_json") or {}
    dominant = triage.get("dominant_bucket")

    results = run_all_lenses_for_round(
        economic_rationale=str(h.get("economic_rationale") or ""),
        mechanism_json=h.get("mechanism_json") or {},
        feature_definition_json=h.get("feature_definition_json") or {},
        quality_context=qctx_full,
        residual_link_count=len(links),
        dominant_bucket=dominant if isinstance(dominant, str) else None,
        hypothesis_title=str(h.get("hypothesis_title") or ""),
        include_compression=True,
    )
    rows = apply_lens_results_to_rows(hypothesis_id, next_round, results)
    dbrec.insert_research_reviews_batch(client, rows)

    now = datetime.now(timezone.utc).isoformat()
    dbrec.update_research_hypothesis(
        client,
        hypothesis_id,
        {
            "status": "under_review",
            "review_rounds_completed": next_round,
            "updated_at": now,
        },
    )
    return {"ok": True, "round": next_round, "reviews_inserted": len(rows)}


def run_referee(client: Any, *, hypothesis_id: str) -> dict[str, Any]:
    h = dbrec.fetch_research_hypothesis(client, hypothesis_id)
    if not h:
        return {"ok": False, "error": "hypothesis_not_found"}
    reviews = dbrec.fetch_research_reviews_for_hypothesis(client, hypothesis_id)
    if not reviews:
        return {"ok": False, "error": "no_reviews_run_review_first"}

    prog = dbrec.fetch_research_program(client, str(h["program_id"]))
    qctx = (prog or {}).get("linked_quality_context_json") or {}
    if qctx.get("public_core_cycle_quality_run_id"):
        row = dbrec.fetch_public_core_cycle_quality_run_by_id(
            client, str(qctx["public_core_cycle_quality_run_id"])
        )
        if row:
            qctx = {
                **qctx,
                "quality_class": row.get("quality_class"),
                "metrics_json": row.get("metrics_json"),
            }

    out = decide_referee(reviews=reviews, quality_context=qctx)
    now = datetime.now(timezone.utc).isoformat()
    dbrec.insert_research_referee_decision(
        client,
        {
            "hypothesis_id": hypothesis_id,
            "final_decision": out["final_decision"],
            "rationale": out["rationale"],
            "disagreement_json": out["disagreement_json"],
            "next_step_json": out["next_step_json"],
            "created_at": now,
        },
    )
    status_map = {
        "kill": "killed",
        "sandbox": "sandboxed",
        "candidate_recipe": "candidate_recipe",
    }
    dbrec.update_research_hypothesis(
        client,
        hypothesis_id,
        {"status": status_map[out["final_decision"]], "updated_at": now},
    )
    return {"ok": True, **out}


def export_dossier_for_program(client: Any, *, program_id: str) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found"}
    hyps = dbrec.fetch_research_hypotheses_for_program(client, program_id)
    reviews = dbrec.fetch_research_reviews_for_program(client, program_id)
    refs = dbrec.fetch_research_referee_for_program(client, program_id)
    links = dbrec.fetch_research_residual_links_for_program(client, program_id)
    return {
        "ok": True,
        "dossier": build_dossier(
            program=prog,
            hypotheses=hyps,
            reviews=reviews,
            referee_decisions=refs,
            residual_links=links,
        ),
    }
