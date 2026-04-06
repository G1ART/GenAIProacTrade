"""Assemble research dossier JSON (Phase 14 evidence bundle)."""

from __future__ import annotations

from typing import Any


def build_dossier(
    *,
    program: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    referee_decisions: list[dict[str, Any]],
    residual_links: list[dict[str, Any]],
) -> dict[str, Any]:
    by_h: dict[str, list[dict[str, Any]]] = {}
    for r in reviews:
        hid = str(r.get("hypothesis_id") or "")
        by_h.setdefault(hid, []).append(r)
    ref_by_h = {str(d.get("hypothesis_id") or ""): d for d in referee_decisions}
    link_by_h: dict[str, list[dict[str, Any]]] = {}
    for link in residual_links:
        hid = str(link.get("hypothesis_id") or "")
        link_by_h.setdefault(hid, []).append(link)

    hyp_sections: list[dict[str, Any]] = []
    explicit_unknowns: list[str] = []
    survived = False
    for h in hypotheses:
        hid = str(h.get("id") or "")
        ref = ref_by_h.get(hid) or {}
        dec = str(ref.get("final_decision") or "")
        if dec == "candidate_recipe":
            survived = True
        dj = ref.get("disagreement_json") or {}
        if isinstance(dj, dict) and dj.get("unresolved_objections"):
            explicit_unknowns.extend(str(x) for x in dj["unresolved_objections"] if x)
        hyp_sections.append(
            {
                "hypothesis": {
                    "id": hid,
                    "title": h.get("hypothesis_title"),
                    "status": h.get("status"),
                    "economic_rationale": h.get("economic_rationale"),
                },
                "reviews_by_round": _group_rounds(by_h.get(hid, [])),
                "referee": ref,
                "residual_links": link_by_h.get(hid, []),
            }
        )

    return {
        "program_question": program.get("research_question"),
        "program_title": program.get("title"),
        "horizon_type": program.get("horizon_type"),
        "universe_name": program.get("universe_name"),
        "linked_quality_context": program.get("linked_quality_context_json"),
        "hypotheses_dossier": hyp_sections,
        "explicit_unknowns": explicit_unknowns,
        "any_candidate_recipe_survived": survived,
        "disclaimer": (
            "Research-stage only. No automatic promotion to product scoring or watchlist ranking."
        ),
    }


def _group_rounds(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    g: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        k = str(r.get("round_number") or "0")
        g.setdefault(k, []).append(r)
    return g
