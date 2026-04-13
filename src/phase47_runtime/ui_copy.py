"""User-first copy, status translation, and surface composition (Phase 47b).

DESIGN.md is the product constitution; this module is the machine-facing translation
layer used by API + static UI. Internal codes may appear only under Advanced.
"""

from __future__ import annotations

from typing import Any

# Forbidden in default user-facing strings (governed conversation + surface).
FORBIDDEN_LEGACY_OPTIMISTIC_TOKENS = (
    "continue_bounded_falsifier_retest_or_narrow_claims_v1",
    "substrate_backfill_or_narrow_claims_then_retest_v1",
)

STATUS_TRANSLATIONS: dict[str, str] = {
    "deferred_due_to_proxy_limited_falsifier_substrate": (
        "Evidence is still too limited for a stronger claim"
    ),
    "closed_pending_new_evidence": "Closed until new evidence arrives",
    "material_falsifier_improvement: false": (
        "The latest pass did not materially improve decision-quality evidence"
    ),
    "optimistic_sector_relabel_only": (
        "Diagnosis improved, but the decision state did not materially improve"
    ),
    "narrow_claims_document_proxy_limits_operator_closeout_v1": (
        "Keep claims narrow and hold until stronger evidence appears"
    ),
    "hold_closeout_until_named_new_source_or_new_evidence_v1": (
        "Hold the closeout until a new named source or new evidence is registered"
    ),
    "deferred": "Deferred — waiting on stronger substrate or evidence",
    "watching_for_new_evidence": "Watching for new evidence",
    "claim_narrowed_closed": "Claims are narrowed; case treated as closed under current evidence",
}

PRIMARY_NAVIGATION: list[dict[str, str]] = [
    {"id": "brief", "label": "Brief", "user_question": "What is this? What should I do?"},
    {"id": "object", "label": "This object", "user_question": "Drill into one cohort or symbol"},
    {"id": "alerts", "label": "Alerts", "user_question": "What needs attention?"},
    {"id": "history", "label": "History", "user_question": "Decisions and trail"},
    {
        "id": "replay",
        "label": "Replay",
        "user_question": "What happened on a time axis — knowable then, not hypothetical",
    },
    {"id": "ask_ai", "label": "Ask AI", "user_question": "Bounded decision copilot"},
]

OBJECT_DETAIL_SECTIONS: list[dict[str, str]] = [
    {"id": "brief", "label": "Brief", "maps_internal": "decision + message (summary)"},
    {"id": "why_now", "label": "Why now", "maps_internal": "message + headline / what_changed"},
    {"id": "what_could_change", "label": "What could change", "maps_internal": "next_watchpoints + closeout card"},
    {"id": "evidence", "label": "Evidence", "maps_internal": "information + research layers"},
    {"id": "history", "label": "History", "maps_internal": "alerts + decisions (links)"},
    {"id": "ask_ai", "label": "Ask AI", "maps_internal": "governed_conversation"},
    {"id": "advanced", "label": "Advanced", "maps_internal": "provenance + closeout + raw drilldown JSON"},
]

OBJECT_HIERARCHY: list[dict[str, str]] = [
    {"kind": "opportunity", "label": "Opportunity", "hint": "Enough evidence to deserve serious attention (not necessarily buy)."},
    {"kind": "watchlist_item", "label": "Watchlist item", "hint": "Worth watching; not decision-ready."},
    {"kind": "closed_research_fixture", "label": "Closed research fixture", "hint": "Closed / deferred / claim-narrowed — not an actionable pitch."},
    {"kind": "alert", "label": "Alert", "hint": "Time- or state-based signal."},
    {"kind": "decision_log_entry", "label": "Decision log entry", "hint": "Recorded founder/operator decision."},
]

ACTION_FRAMING_EXAMPLES: list[str] = [
    "No action",
    "Keep watching",
    "Review new evidence",
    "Research closed",
    "Decision-ready",
    "Consider reopen request",
]

ADVANCED_BOUNDARY_RULES: list[str] = [
    "Raw JSON, internal layer keys, and file paths appear only under Advanced.",
    "Default cards use plain language from the translation layer.",
    "Gate codes and stance tokens are summarized first; verbatim codes are optional in Advanced.",
]


def translate_token(token: str | None) -> str:
    if not token:
        return ""
    t = str(token).strip()
    if t in STATUS_TRANSLATIONS:
        return STATUS_TRANSLATIONS[t]
    # partial contains
    low = t.lower()
    for k, v in STATUS_TRANSLATIONS.items():
        if k.lower() in low:
            return v
    return t


def infer_object_kind(bundle: dict[str, Any]) -> str:
    rm = bundle.get("founder_read_model") or {}
    aid = str(rm.get("asset_id") or "").lower()
    closeout = str(rm.get("closeout_status") or "").lower()
    if "fixture" in aid or "research_engine_fixture" in aid:
        return "closed_research_fixture"
    if closeout.startswith("closed") or "closeout" in closeout:
        return "closed_research_fixture"
    st = str(rm.get("decision_status") or rm.get("current_stance") or "").lower()
    if "watch" in st:
        return "watchlist_item"
    return "cohort_research_object"


def object_kind_label(kind: str) -> str:
    for row in OBJECT_HIERARCHY:
        if row["kind"] == kind:
            return row["label"]
    return "Research object"


def action_framing(bundle: dict[str, Any]) -> str:
    rm = bundle.get("founder_read_model") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    primary = str(agg.get("founder_primary_status") or rm.get("decision_status") or "")
    closeout = str(rm.get("closeout_status") or "")
    kind = infer_object_kind(bundle)

    if kind == "closed_research_fixture":
        if rm.get("reopen_requires_named_source"):
            return "Consider reopen request — only with a new named source path"
        return "Research closed — hold until new evidence or named source"
    if primary == "watching_for_new_evidence" or "watch" in primary.lower():
        return "Keep watching"
    if "defer" in primary.lower():
        return "No action — deferred"
    return "Review new evidence"


def build_user_first_brief(bundle: dict[str, Any]) -> dict[str, Any]:
    rm = bundle.get("founder_read_model") or {}
    pitch = bundle.get("representative_pitch") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    dc = agg.get("decision_card") or {}
    gate = (rm.get("gate_summary") or {}) if isinstance(rm.get("gate_summary"), dict) else {}
    pbc = gate.get("primary_block_category")

    kind = infer_object_kind(bundle)
    one_line = (dc.get("body") or rm.get("headline_message") or pitch.get("top_level_pitch") or "").strip()
    stance_plain = translate_token(str(rm.get("current_stance") or ""))
    gate_plain = translate_token(str(pbc) if pbc else "")

    return {
        "object_kind": kind,
        "object_kind_label": object_kind_label(kind),
        "object_kind_hint": next((x["hint"] for x in OBJECT_HIERARCHY if x["kind"] == kind), ""),
        "stance_plain": stance_plain or str(rm.get("current_stance") or ""),
        "one_line_explanation": one_line[:2000],
        "action_framing": action_framing(bundle),
        "evidence_state_plain": gate_plain or translate_token(str(gate.get("gate_status") or "")),
        "asset_id": rm.get("asset_id"),
        "symbols_preview": (rm.get("cohort_symbols") or [])[:12],
    }


def build_section_payload(bundle: dict[str, Any], section: str) -> dict[str, Any]:
    """Compose one user-first section from Phase 46 bundle fields + drilldown."""
    rm = bundle.get("founder_read_model") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    dd = bundle.get("drilldown_examples") or {}
    pitch = bundle.get("representative_pitch") or {}

    brief = build_user_first_brief(bundle)
    out: dict[str, Any] = {
        "section": section,
        "object_kind_label": brief["object_kind_label"],
        "action_framing": brief["action_framing"],
    }

    if section == "brief":
        out["paragraphs"] = [
            f"**{brief['object_kind_label']}** — {brief['object_kind_hint']}",
            f"**Current stance (plain):** {brief['stance_plain']}",
            f"**What the system is saying:** {brief['one_line_explanation'][:1200]}",
            f"**What to do now:** {brief['action_framing']}",
            f"**Evidence state:** {brief['evidence_state_plain'] or 'See Evidence tab'}",
        ]
        return out

    if section == "why_now":
        wc = rm.get("what_changed") or []
        out["bullets_changed"] = [str(x) for x in wc][:20]
        mc = agg.get("message_card") or {}
        out["message_summary"] = str(mc.get("body") or rm.get("headline_message") or "")[:2500]
        out["intro"] = (
            "This object is on screen because it is part of your governed cockpit loadout "
            "and has a defined research stance. Recent changes below are from the latest authoritative bundle."
        )
        return out

    if section == "what_could_change":
        nw = rm.get("next_watchpoints") or []
        crc = agg.get("closeout_reopen_card") or {}
        out["watchpoints_plain"] = [translate_token(str(x)) for x in nw][:20]
        out["reopen_note"] = str(crc.get("reopen_note") or "")[:2000]
        out["closeout_plain"] = translate_token(str(crc.get("closeout") or rm.get("closeout_status") or ""))
        return out

    if section == "evidence":
        ic = agg.get("information_card") or {}
        rp = agg.get("research_provenance_card") or {}
        out["key_facts"] = [str(x) for x in (ic.get("bullets") or [])][:20]
        out["limits_and_provenance"] = [str(x) for x in (rp.get("bullets") or [])][:20]
        wnc = rm.get("what_did_not_change") or []
        unc = rm.get("current_uncertainties") or []
        out["what_did_not_change"] = [str(x) for x in wnc][:15]
        out["what_remains_unproven"] = [str(x) for x in unc][:15]
        return out

    if section == "history":
        out["intro"] = "Alerts and recorded decisions live in their own panels (History navigation)."
        out["links"] = [
            {"panel": "alerts", "label": "Open Alerts panel"},
            {"panel": "history", "label": "Open decision log"},
        ]
        return out

    if section == "ask_ai":
        out["intro"] = "Use quick prompts below — responses are governed and grounded in the bundle (not generic chat)."
        out["shortcuts"] = governed_prompt_shortcuts()
        return out

    if section == "advanced":
        out["internal_layers"] = list(dd.keys())
        out["raw_drilldown"] = {k: dd[k] for k in dd}
        out["layer_summaries"] = pitch.get("layer_summaries") or {}
        out["trace_links"] = rm.get("trace_links") or {}
        return out

    return {**out, "error": "unknown_section"}


def governed_prompt_shortcuts() -> list[dict[str, str]]:
    return [
        {"label": "Explain this briefly", "text": "decision summary"},
        {"label": "Show key evidence", "text": "information layer"},
        {"label": "Why is this closed?", "text": "why is this closed"},
        {"label": "What changed?", "text": "what changed"},
        {"label": "What could change?", "text": "what could change"},
        {"label": "Show research history", "text": "research layer"},
        {"label": "Log context (provenance)", "text": "show provenance"},
    ]


def navigation_contract() -> dict[str, Any]:
    return {
        "primary_navigation": PRIMARY_NAVIGATION,
        "object_detail_sections": OBJECT_DETAIL_SECTIONS,
        "internal_layers": ["decision", "message", "information", "research", "provenance", "closeout"],
    }
