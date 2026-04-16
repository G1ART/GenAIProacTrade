"""Controlled intents only — map to bundle drill-down and pitch; no free-form generation."""

from __future__ import annotations

import json
import re
from typing import Any

from phase46.representative_agent import assert_pitch_governed

_FORBIDDEN = (
    "continue_bounded_falsifier_retest_or_narrow_claims_v1",
    "substrate_backfill_or_narrow_claims_then_retest_v1",
)

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("decision_summary", [r"\bdecision\s+summary\b", r"\bstance\b", r"\bcurrent\s+stance\b"]),
    ("information_layer", [r"\binformation\s+layer\b", r"\bkey\s+facts\b"]),
    ("research_layer", [r"\bresearch\s+layer\b", r"\bmaterial\s+falsifier\b"]),
    ("why_closed", [r"\bwhy\s+is\s+this\s+closed\b", r"\bwhy\s+closed\b"]),
    ("provenance", [r"\bshow\s+provenance\b", r"\bprovenance\b", r"\btrace\b"]),
    ("what_changed", [r"\bwhat\s+changed\b"]),
    ("what_unproven", [r"\bwhat\s+remains\s+unproven\b", r"\bunproven\b"]),
    ("why_now", [r"\bwhy\s+now\b"]),
    ("what_to_watch", [r"\bwhat\s+to\s+watch\b"]),
    ("message_layer", [r"\bmessage\s+layer\b", r"\bchief\b", r"\bpitch\b"]),
    ("closeout_layer", [r"\bcloseout\b", r"\breopen\b", r"\bwhat\s+could\s+change\b"]),
]


def _detect_intent(text: str) -> str | None:
    t = text.strip().lower()
    if not t:
        return None
    for intent, pats in _INTENT_PATTERNS:
        for pat in pats:
            if re.search(pat, t):
                return intent
    return None


def _fmt_list(items: Any) -> str:
    if not items:
        return "_No entries._"
    if isinstance(items, list):
        lines = []
        for x in items:
            if isinstance(x, str):
                lines.append(f"- {x}")
            elif isinstance(x, dict):
                lines.append(f"- {json.dumps(x, ensure_ascii=False)[:500]}")
            else:
                lines.append(f"- {x!s}")
        return "\n".join(lines) if lines else "_No entries._"
    return str(items)


def build_governed_conversation_contract() -> dict[str, Any]:
    return {
        "version": 1,
        "description": "Founder prompts are matched to governed bundle slices only; no LLM.",
        "intents_supported": [name for name, _ in _INTENT_PATTERNS],
        "fallback": "outside_governed_cockpit_scope",
        "optional_request_fields": ["copilot_context"],
    }


_SAFE_COPILOT_KEYS = frozenset(
    {
        "source",
        "asset_id",
        "horizon",
        "horizon_label",
        "active_model_family",
        "as_of_utc",
        "spectrum_band",
        "spectrum_quintile",
        "spectrum_position",
        "rank_index",
        "rank_movement",
        "headline",
        "message_summary",
        "valuation_tension",
        "why_now",
        "what_to_watch",
        "what_remains_unproven",
        "replay_lineage_pointer",
        "message_snapshot_id",
        "linked_registry_entry_id",
        "linked_artifact_id",
        "challenger_hint",
    }
)


def _sanitize_copilot_context(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        key = k.strip()[:64]
        if key not in _SAFE_COPILOT_KEYS:
            continue
        s = str(v).strip().replace("\n", " ").replace("**", "")
        if len(s) > 500:
            s = s[:497] + "..."
        if s:
            out[key] = s
    return out


def _copilot_context_markdown_prefix(ctx: dict[str, str]) -> str:
    if not ctx:
        return ""
    order = [
        "source",
        "asset_id",
        "horizon",
        "horizon_label",
        "spectrum_band",
        "spectrum_quintile",
        "spectrum_position",
        "rank_index",
        "rank_movement",
        "active_model_family",
        "as_of_utc",
        "headline",
        "message_summary",
        "valuation_tension",
        "why_now",
        "what_to_watch",
        "what_remains_unproven",
        "replay_lineage_pointer",
        "message_snapshot_id",
        "linked_registry_entry_id",
        "linked_artifact_id",
        "challenger_hint",
    ]
    lines = ["## Copilot context (UI)", ""]
    seen: set[str] = set()
    for k in order:
        if k in ctx and ctx[k]:
            label = k.replace("_", " ").title()
            lines.append(f"- **{label}**: {ctx[k]}")
            seen.add(k)
    for k in sorted(ctx.keys()):
        if k in seen or not ctx[k]:
            continue
        lines.append(f"- **{k}**: {ctx[k]}")
    return "\n".join(lines) + "\n\n---\n\n"


def _apply_copilot_prefix(out: dict[str, Any], copilot_context: dict[str, str] | None) -> dict[str, Any]:
    prefix = _copilot_context_markdown_prefix(copilot_context or {})
    if not prefix:
        return out
    body = str(out.get("body_markdown") or "")
    out = {**out, "body_markdown": (prefix + body).strip()}
    return out


def process_governed_prompt(
    bundle: dict[str, Any],
    user_text: str,
    *,
    copilot_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = _sanitize_copilot_context(copilot_context)
    intent = _detect_intent(user_text)
    rm = bundle.get("founder_read_model") or {}
    pitch = bundle.get("representative_pitch") or {}
    dd = bundle.get("drilldown_examples") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}

    if not intent:
        out = {
            "governed": True,
            "intent": "outside_governed_cockpit_scope",
            "title": "Outside governed scope",
            "body_markdown": (
                "This cockpit only answers **governed prompts** mapped to the Phase 46 bundle "
                "(decision summary, information / research / message / closeout layers, provenance, "
                "what changed, what remains unproven). Rephrase using those phrases, or use the "
                "tabs for structured views."
            ),
            "structured": {},
        }
        assert_pitch_governed(out["title"] + "\n" + out["body_markdown"])
        return _apply_copilot_prefix(out, ctx)

    if intent == "decision_summary":
        card = agg.get("decision_card") or {}
        layer = dd.get("decision") or {}
        body = f"**{card.get('title', 'Decision')}**\n\n{card.get('body', '')}\n\n---\n\n{layer.get('summary', '')}"
        structured = {"decision_card": card, "drilldown_structured": layer.get("structured")}
    elif intent == "information_layer":
        layer = dd.get("information") or {}
        inf = agg.get("information_card") or {}
        body = f"**{inf.get('title', 'Information')}**\n\n{_fmt_list(inf.get('bullets'))}\n\n---\n\n{layer.get('summary', '')}"
        structured = {"information_card": inf, "drilldown_structured": layer.get("structured")}
    elif intent == "research_layer":
        layer = dd.get("research") or {}
        rpc = agg.get("research_provenance_card") or {}
        rpc_body = rpc.get("body") or _fmt_list(rpc.get("bullets"))
        body = f"**{rpc.get('title', 'Research')}**\n\n{rpc_body}\n\n---\n\n{layer.get('summary', '')}"
        structured = {"research_provenance_card": rpc, "drilldown_structured": layer.get("structured")}
    elif intent == "why_closed" or intent == "closeout_layer":
        layer = dd.get("closeout") or {}
        crc = agg.get("closeout_reopen_card") or {}
        crc_body = crc.get("body") or "\n".join(
            f"- {k}: {v}"
            for k, v in crc.items()
            if k != "title" and v is not None
        )
        body = f"**{crc.get('title', 'Closeout')}**\n\n{crc_body}\n\n---\n\n{layer.get('summary', '')}"
        structured = {"closeout_reopen_card": crc, "drilldown_structured": layer.get("structured")}
    elif intent == "provenance":
        layer = dd.get("provenance") or {}
        body = layer.get("summary", "") + "\n\n**Trace links**\n" + _fmt_list(rm.get("trace_links"))
        structured = layer.get("structured") or {}
    elif intent == "what_changed":
        body = "**What changed**\n\n" + _fmt_list(rm.get("what_changed"))
        body += "\n\n**What did not change**\n\n" + _fmt_list(rm.get("what_did_not_change"))
        structured = {"what_changed": rm.get("what_changed"), "what_did_not_change": rm.get("what_did_not_change")}
    elif intent == "what_unproven":
        body = str(pitch.get("what_remains_unproven") or "")
        structured = {"what_remains_unproven": pitch.get("what_remains_unproven")}
    elif intent == "why_now":
        wn = str(ctx.get("why_now") or ctx.get("headline") or "").strip()
        if not wn:
            wn = str(rm.get("headline_message") or "").strip()
        body = "**Why now**\n\n" + (wn or "_No Today row context — open a spectrum row or pass copilot_context._")
        structured = {"why_now": wn}
    elif intent == "what_to_watch":
        wt = str(ctx.get("what_to_watch") or "").strip()
        if not wt:
            wt = str(pitch.get("what_to_watch") or "").strip()
        body = "**What to watch**\n\n" + (wt or "_No watch list from Today context — use copilot_context or bundle pitch._")
        structured = {"what_to_watch": wt}
    else:
        layer = dd.get("message") or {}
        body = str(pitch.get("top_level_pitch") or layer.get("summary") or "")
        body += "\n\n**Why this matters**\n\n" + str(pitch.get("why_this_matters") or "")
        structured = {"why_this_matters": pitch.get("why_this_matters")}

    blob = intent + json.dumps(structured, ensure_ascii=False, default=str) + body
    assert_pitch_governed(blob)
    for bad in _FORBIDDEN:
        if bad.lower() in blob.lower():
            raise ValueError(f"governed conversation leaked forbidden token: {bad}")

    out = {
        "governed": True,
        "intent": intent,
        "title": intent.replace("_", " ").title(),
        "body_markdown": body.strip(),
        "structured": structured,
    }
    return _apply_copilot_prefix(out, ctx)


def list_intent_registry() -> list[dict[str, str]]:
    return [{"intent": name, "description": f"Patterns: {', '.join(pats[:2])}…"} for name, pats in _INTENT_PATTERNS]
