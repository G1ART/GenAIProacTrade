"""Deterministic governed spokesperson — authoritative artifacts only, no LLM."""

from __future__ import annotations

from typing import Any

# Must never appear in founder-facing pitch (legacy Phase 43 / nested optimism)
_FORBIDDEN_IN_PITCH = (
    "continue_bounded_falsifier_retest_or_narrow_claims_v1",
    "substrate_backfill_or_narrow_claims_then_retest_v1",
)


def assert_pitch_governed(pitch_text: str) -> None:
    low = pitch_text.lower()
    for bad in _FORBIDDEN_IN_PITCH:
        if bad.lower() in low:
            raise ValueError(f"governed pitch leaked forbidden legacy token: {bad}")


def build_representative_pitch(
    *,
    founder_read_model: dict[str, Any],
    cockpit_state: dict[str, Any],
    phase45_bundle: dict[str, Any],
) -> dict[str, Any]:
    ar = phase45_bundle.get("authoritative_resolution") or {}
    rationale = str(ar.get("authoritative_rationale") or "")
    p46 = phase45_bundle.get("phase46") or {}

    top = (
        "Chief-of-staff read: the research engine holds a **closed, claim-narrowed** posture on the 8-row "
        "fixture cohort. Falsifier substrate remains proxy-limited; we are **not** reopening broad public-core "
        "work. Next step is to **hold** until a **named new source or path** (or other dispositive evidence) is "
        "registered under governance — not to infer urgency from older bundle recommendation strings."
    )

    why = (
        "This matters because promotion and external claims must track **Phase 44 authoritative truthfulness** "
        "and **Phase 45 canonical closeout**. Misreading legacy optimistic wording in Phase 43 bundles would "
        "overstate how much the last bounded pass improved falsifiers."
    )

    agg = cockpit_state.get("cohort_aggregate") or {}
    what_changed = founder_read_model.get("what_changed") or []
    what_not = founder_read_model.get("what_did_not_change") or []

    unproven = (
        "Still unproven for this cohort: clean pre-signal filing-public picks at strict PIT, and "
        "sector-informed stratification — aggregate scorecards did not gain exact_public_ts_available or "
        "sector_available in the Phase 43 bracket."
    )

    watch = "; ".join(founder_read_model.get("next_watchpoints") or [])[:1200]

    pitch = {
        "top_level_pitch": top,
        "why_this_matters": why,
        "what_changed": what_changed,
        "what_remains_unproven": unproven,
        "what_to_watch_next": watch,
        "authoritative_rationale_excerpt": rationale[:1500],
        "phase46_default": p46.get("phase46_recommendation"),
    }

    combined = "\n\n".join(
        str(pitch[k])
        for k in (
            "top_level_pitch",
            "why_this_matters",
            "what_changed",
            "what_remains_unproven",
            "what_to_watch_next",
            "authoritative_rationale_excerpt",
            "phase46_default",
        )
    )
    assert_pitch_governed(combined)

    pitch["layer_summaries"] = {
        "decision": _summarize_decision(founder_read_model),
        "message": top[:800],
        "information": "\n".join(f"- {b}" for b in (agg.get("information_card") or {}).get("bullets") or []),
        "research": "\n".join(
            f"- {b}" for b in (agg.get("research_provenance_card") or {}).get("bullets") or []
        ),
        "provenance": (
            "Trace: Phase 45 canonical bundle records which Phase 43 fields were superseded; "
            "Phase 44 bundle holds provenance-separated audits. Drill-down `provenance` for paths."
        ),
        "closeout": str((agg.get("closeout_reopen_card") or {}).get("closeout") or ""),
    }

    return pitch


def _summarize_decision(rm: dict[str, Any]) -> str:
    return (
        f"Stance: {rm.get('decision_status')} | Authoritative phase: {rm.get('authoritative_phase')} | "
        f"Recommendation key: {rm.get('authoritative_recommendation')}"
    )
