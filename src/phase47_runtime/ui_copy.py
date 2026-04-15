"""User-first copy, status translation, and surface composition (Phase 47b).

DESIGN.md is the product constitution; this module is the machine-facing translation
layer used by API + static UI. Internal codes may appear only under Advanced.
"""

from __future__ import annotations

from typing import Any

from phase47_runtime.phase47e_user_locale import (
    ACTION_FRAMING,
    SECTION_LABELS,
    governed_prompt_shortcuts_localized,
    normalize_lang,
    object_kind_hint_localized,
    object_kind_label_localized,
    shell_nav_rows,
    translate_status_token,
    t as locale_t,
)

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


def translate_token(token: str | None, lang: str | None = None) -> str:
    return translate_status_token(lang, token)


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


def object_kind_label(kind: str, lang: str | None = None) -> str:
    return object_kind_label_localized(lang, kind)


def action_framing(bundle: dict[str, Any], lang: str | None = None) -> str:
    lg = normalize_lang(lang)
    msgs = ACTION_FRAMING.get(lg) or ACTION_FRAMING["en"]
    rm = bundle.get("founder_read_model") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    primary = str(agg.get("founder_primary_status") or rm.get("decision_status") or "")
    kind = infer_object_kind(bundle)

    if kind == "closed_research_fixture":
        if rm.get("reopen_requires_named_source"):
            return msgs["closed_reopen"]
        return msgs["closed_hold"]
    if primary == "watching_for_new_evidence" or "watch" in primary.lower():
        return msgs["keep_watching"]
    if "defer" in primary.lower():
        return msgs["defer"]
    return msgs["review"]


def build_user_first_brief(bundle: dict[str, Any], lang: str | None = None) -> dict[str, Any]:
    lg = normalize_lang(lang)
    rm = bundle.get("founder_read_model") or {}
    pitch = bundle.get("representative_pitch") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    dc = agg.get("decision_card") or {}
    gate = (rm.get("gate_summary") or {}) if isinstance(rm.get("gate_summary"), dict) else {}
    pbc = gate.get("primary_block_category")

    kind = infer_object_kind(bundle)
    one_line = (dc.get("body") or rm.get("headline_message") or pitch.get("top_level_pitch") or "").strip()
    stance_plain = translate_token(str(rm.get("current_stance") or ""), lang=lg)
    gate_plain = translate_token(str(pbc) if pbc else "", lang=lg)

    return {
        "object_kind": kind,
        "object_kind_label": object_kind_label_localized(lg, kind),
        "object_kind_hint": object_kind_hint_localized(lg, kind),
        "stance_plain": stance_plain or str(rm.get("current_stance") or ""),
        "one_line_explanation": one_line[:2000],
        "action_framing": action_framing(bundle, lang=lg),
        "evidence_state_plain": gate_plain or translate_token(str(gate.get("gate_status") or ""), lang=lg),
        "asset_id": rm.get("asset_id"),
        "symbols_preview": (rm.get("cohort_symbols") or [])[:12],
    }


def build_section_payload(bundle: dict[str, Any], section: str, lang: str | None = None) -> dict[str, Any]:
    """Compose one user-first section from Phase 46 bundle fields + drilldown."""
    rm = bundle.get("founder_read_model") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}
    dd = bundle.get("drilldown_examples") or {}
    pitch = bundle.get("representative_pitch") or {}

    lg = normalize_lang(lang)
    brief = build_user_first_brief(bundle, lang=lg)
    out: dict[str, Any] = {
        "section": section,
        "object_kind_label": brief["object_kind_label"],
        "action_framing": brief["action_framing"],
    }

    if section == "brief":
        out["paragraphs"] = [
            f"**{brief['object_kind_label']}** — {brief['object_kind_hint']}",
            f"**{locale_t(lg, 'brief.label_stance')}:** {brief['stance_plain']}",
            f"**{locale_t(lg, 'brief.label_saying')}:** {brief['one_line_explanation'][:1200]}",
            f"**{locale_t(lg, 'brief.label_action')}:** {brief['action_framing']}",
            f"**{locale_t(lg, 'brief.label_evidence')}:** {brief['evidence_state_plain'] or locale_t(lg, 'brief.evidence_fallback')}",
        ]
        return out

    if section == "why_now":
        wc = rm.get("what_changed") or []
        out["bullets_changed"] = [str(x) for x in wc][:20]
        mc = agg.get("message_card") or {}
        out["message_summary"] = str(mc.get("body") or rm.get("headline_message") or "")[:2500]
        out["intro"] = locale_t(lg, "why_now.intro")
        return out

    if section == "what_could_change":
        nw = rm.get("next_watchpoints") or []
        crc = agg.get("closeout_reopen_card") or {}
        out["watchpoints_plain"] = [translate_token(str(x), lang=lg) for x in nw][:20]
        out["reopen_note"] = str(crc.get("reopen_note") or "")[:2000]
        out["closeout_plain"] = translate_token(str(crc.get("closeout") or rm.get("closeout_status") or ""), lang=lg)
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
        out["intro"] = locale_t(lg, "history.intro")
        out["links"] = [
            {"panel": "advanced", "label": locale_t(lg, "history.link_advanced")},
            {"panel": "journal", "label": locale_t(lg, "history.link_journal")},
        ]
        return out

    if section == "ask_ai":
        out["intro"] = locale_t(lg, "ask_ai.intro")
        out["shortcuts"] = governed_prompt_shortcuts(lg)
        return out

    if section == "advanced":
        out["internal_layers"] = list(dd.keys())
        out["raw_drilldown"] = {k: dd[k] for k in dd}
        out["layer_summaries"] = pitch.get("layer_summaries") or {}
        out["trace_links"] = rm.get("trace_links") or {}
        return out

    return {**out, "error": "unknown_section"}


def governed_prompt_shortcuts(lang: str | None = None) -> list[dict[str, str]]:
    if lang is None:
        return governed_prompt_shortcuts_localized("en")
    return governed_prompt_shortcuts_localized(lang)


def navigation_contract(lang: str | None = None) -> dict[str, Any]:
    lg = normalize_lang(lang)
    tabs = SECTION_LABELS.get(lg, SECTION_LABELS["en"]).get("tabs") or OBJECT_DETAIL_SECTIONS
    return {
        "primary_navigation": shell_nav_rows(lg),
        "object_detail_sections": tabs,
        "internal_layers": ["decision", "message", "information", "research", "provenance", "closeout"],
    }
