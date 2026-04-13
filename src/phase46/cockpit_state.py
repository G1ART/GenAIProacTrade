"""Cockpit cards: decision / message / information / research / closeout-reopen."""

from __future__ import annotations

from typing import Any

# Founder-facing statuses (not raw gate strings as primary label)
STATUS_TRACKING = "tracking"
STATUS_WATCHING = "watching_for_new_evidence"
STATUS_REOPEN_IF_REGISTERED = "bounded_reopen_available_if_registered"
STATUS_CLAIM_NARROWED = "claim_narrowed_closed"
STATUS_DECISION_READY = "decision_ready"
STATUS_DEFERRED_PROXY = "deferred_proxy_limited"


def build_cockpit_state(
    *,
    founder_read_model: dict[str, Any],
    phase45_bundle: dict[str, Any],
    phase44_bundle: dict[str, Any],
) -> dict[str, Any]:
    gate = founder_read_model.get("gate_summary") or {}
    closeout = founder_read_model.get("closeout_status") or ""
    p46 = phase45_bundle.get("phase46") or {}
    fr = phase45_bundle.get("future_reopen_protocol") or {}

    primary = STATUS_WATCHING if closeout == "closed_pending_new_evidence" else STATUS_TRACKING
    if gate.get("primary_block_category"):
        research_tag = STATUS_DEFERRED_PROXY
    else:
        research_tag = STATUS_TRACKING

    reopen_note = (
        "A single bounded retest may be authorized only after registering a named source/path "
        "materially different from Phase 43 filing repair and Yahoo chart sector hydration."
        if fr.get("future_reopen_allowed_with_named_source")
        else "Reopen protocol inactive."
    )

    cohort_aggregate = {
        "founder_primary_status": primary,
        "research_substrate_tag": research_tag,
        "claim_narrowing_tag": STATUS_CLAIM_NARROWED,
        "decision_card": {
            "title": "Current stance",
            "body": founder_read_model.get("headline_message"),
            "stance_code": founder_read_model.get("current_stance"),
            "authoritative_phase": founder_read_model.get("authoritative_phase"),
        },
        "message_card": {
            "title": "Operator-facing summary",
            "body": _message_body(founder_read_model),
        },
        "information_card": {
            "title": "Key facts",
            "bullets": _info_bullets(founder_read_model, phase44_bundle),
        },
        "research_provenance_card": {
            "title": "Research provenance",
            "bullets": [
                "Authoritative interpretation: Phase 44 truthfulness bundle (Phase 45 precedence record).",
                "Phase 43 nested optimistic retry strings are historical only; do not use for current guidance.",
                f"Gate (drill-down): {gate.get('gate_status')} / {gate.get('primary_block_category')}",
            ],
        },
        "closeout_reopen_card": {
            "title": "Closeout & reopen",
            "closeout": closeout,
            "phase46_next": p46.get("phase46_recommendation"),
            "reopen_note": reopen_note,
        },
    }

    row_cards: list[dict[str, Any]] = []
    for sym in founder_read_model.get("cohort_symbols") or []:
        row_cards.append(
            {
                "asset_id": f"fixture_row:{sym}",
                "symbol": sym,
                "founder_primary_status": primary,
                "decision_card": {
                    "title": f"{sym} — fixture row",
                    "body": "Same cohort-level governance and closeout apply; row-level drill-down in research layer.",
                },
                "message_card": {
                    "title": "Message",
                    "body": cohort_aggregate["message_card"]["body"],
                },
                "information_card": {
                    "title": "Facts",
                    "bullets": [f"Member of {founder_read_model.get('cohort_row_count')}-row join-mismatch fixture."],
                },
                "research_provenance_card": cohort_aggregate["research_provenance_card"],
                "closeout_reopen_card": cohort_aggregate["closeout_reopen_card"],
            }
        )

    return {
        "cohort_aggregate": cohort_aggregate,
        "row_cards": row_cards,
        "status_vocabulary": [
            STATUS_TRACKING,
            STATUS_WATCHING,
            STATUS_REOPEN_IF_REGISTERED,
            STATUS_CLAIM_NARROWED,
            STATUS_DECISION_READY,
            STATUS_DEFERRED_PROXY,
        ],
    }


def _message_body(rm: dict[str, Any]) -> str:
    parts = [
        rm.get("headline_message") or "",
        "Uncertainties: " + "; ".join(rm.get("current_uncertainties") or [])[:800],
    ]
    return "\n\n".join(p for p in parts if p)


def _info_bullets(rm: dict[str, Any], p44: dict[str, Any]) -> list[str]:
    truth = p44.get("phase44_truthfulness_assessment") or {}
    bullets = [
        f"Cohort: {rm.get('cohort_row_count')} fixture rows ({', '.join((rm.get('cohort_symbols') or [])[:5])}{'…' if len(rm.get('cohort_symbols') or []) > 5 else ''}).",
        f"Material falsifier improvement (Phase 44): {truth.get('material_falsifier_improvement')}.",
        f"Authoritative recommendation: {rm.get('authoritative_recommendation')}.",
    ]
    return bullets
