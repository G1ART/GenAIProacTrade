"""Phase 47d — thick-slice Home feed blocks, shell nav contract, copilot brief (DESIGN_V3-aligned)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase46.alert_ledger import list_alerts
from phase46.decision_trace_ledger import list_decisions

from phase47_runtime.phase47e_user_locale import (
    ask_ai_brief_contract_localized,
    normalize_lang,
    phase47f_recommend,
    t,
)
from phase47_runtime.frozen_snapshot_pack_v0 import load_frozen_snapshot_pack_v0
from phase47_runtime.today_spectrum import (
    build_today_spectrum_summary_for_home,
    expand_watchlist_for_spectrum_filter,
    list_spectrum_seed_asset_ids,
    load_spectrum_watch_alias_map,
)
from phase47_runtime.watchlist_order_v1 import load_watchlist_order, merge_watchlist_display_order
from phase47_runtime.ui_copy import build_user_first_brief, infer_object_kind, translate_token

# Top shell per Phase 47d work order — internal research labels are not the mental model.
SHELL_NAVIGATION_47D: list[dict[str, str]] = [
    {"id": "home", "label": "Home", "user_question": "What matters now across my surface?"},
    {"id": "watchlist", "label": "Watchlist", "user_question": "What am I tracking and how is it moving?"},
    {"id": "research", "label": "Research", "user_question": "What is being worked on and archived context?"},
    {"id": "replay", "label": "Replay", "user_question": "What happened, knowable then?"},
    {"id": "journal", "label": "Journal", "user_question": "What did I decide and why?"},
    {"id": "ask_ai", "label": "Ask AI", "user_question": "Copilot — bounded, bundle-grounded"},
    {"id": "advanced", "label": "Advanced", "user_question": "Alerts manager, raw references"},
]

HOME_BLOCKS_CATALOG: list[dict[str, str]] = [
    {"id": "today", "label": "Today", "purpose": "What deserves attention now and whether action is needed"},
    {"id": "watchlist", "label": "Watchlist", "purpose": "Tracked cohorts / names and why not yet opportunity"},
    {"id": "research_in_progress", "label": "Research in progress", "purpose": "Active or recent threads — activity feed, not a job table"},
    {"id": "alerts", "label": "Alerts", "purpose": "Signals that need review"},
    {"id": "decision_journal", "label": "Decision journal", "purpose": "Recent decisions with replay link"},
    {"id": "ask_ai_brief", "label": "Ask AI brief", "purpose": "Copilot shortcuts — not a generic chat center"},
    {"id": "replay_preview", "label": "Replay preview", "purpose": "Signature capability on Home — teaser, not full timeline"},
    {"id": "portfolio_snapshot", "label": "Portfolio snapshot", "purpose": "Placeholder — lineage in later phase"},
]

CLOSED_FIXTURE_REPOSITIONING: list[str] = [
    "Closed research fixtures are no longer the dominant Home hero.",
    "They remain reachable under Research → cohort detail and Advanced (archive-style context).",
    "Home 'Today' explains when the loadout is fixture-first and points to Watchlist / Research / Alerts instead.",
]

EMPTY_STATE_RULES_APPLIED: list[str] = [
    "Each Home block ships copy for: what belongs here, why it can be empty, what will populate it later.",
    "No raw JSON as the default block body on Home — summaries and plain lines only.",
    "Advanced is the only top-level area where full alert tooling and raw drilldown appear by default.",
]


def replay_preview_contract() -> dict[str, Any]:
    """Static contract: what Home shows for Replay (DESIGN_V3 — no future leakage in teaser copy)."""
    return {
        "surface": "home_feed_card",
        "includes": [
            "last_decision_teaser_when_available",
            "time_axis_snippet_label_illustrative",
            "what_changed_since_teaser",
            "jump_to_replay_panel",
        ],
        "design_v3": "Teasers use bundle-time summaries and known-then framing; full truth on Replay panel.",
    }


def ask_ai_brief_contract(lang: str | None = None) -> list[dict[str, str]]:
    """Premium copilot brief — shortcuts (label + governed prompt text). Default EN for static bundles/tests."""
    return ask_ai_brief_contract_localized("en" if lang is None else lang)


def bundle_watch_candidate_asset_ids(bundle: dict[str, Any]) -> list[str]:
    """Primary + cohort symbols in bundle order (before user reorder merge)."""
    rm = bundle.get("founder_read_model") or {}
    out: list[str] = []
    pa = str(rm.get("asset_id") or "").strip()
    if pa:
        out.append(pa)
    for s in rm.get("cohort_symbols") or []:
        ss = str(s).strip()
        if ss and ss not in out:
            out.append(ss)
    return out


def _load_recent_jobs(repo_root: Path, *, limit: int = 6) -> list[dict[str, Any]]:
    p = repo_root / "data" / "research_runtime" / "research_job_registry_v1.json"
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        jobs = list(raw.get("jobs") or [])
    except (json.JSONDecodeError, OSError):
        return []
    out: list[dict[str, Any]] = []
    for j in jobs[-limit:]:
        out.append(
            {
                "job_id": str(j.get("job_id") or "")[:36],
                "job_type": str(j.get("job_type") or ""),
                "status": str(j.get("status") or ""),
                "trigger_source": str(j.get("trigger_source") or ""),
                "created_at": str(j.get("created_at") or "")[:19],
                "result_summary": str(j.get("result_summary") or "")[:280],
            }
        )
    return list(reversed(out))


def build_home_feed_payload(state: Any, lang: str | None = None) -> dict[str, Any]:
    """Compose machine + human-readable Home blocks for API + static UI."""
    lg = normalize_lang(lang)
    bundle = state.bundle
    repo_root = state.repo_root
    brief = build_user_first_brief(bundle, lang=lg)
    kind = infer_object_kind(bundle)
    rm = bundle.get("founder_read_model") or {}
    alerts = list_alerts(state.alert_ledger_path)
    decisions = list_decisions(state.decision_ledger_path)
    open_alerts = [a for a in alerts if str(a.get("status") or "") == "open"]
    recent_decs = list(reversed(decisions[-8:]))

    # Today — do not hero closed fixture without context
    if open_alerts:
        a0 = open_alerts[0]
        today_title = t(lg, "today.alert_title")
        today_body = t(lg, "today.open_body").format(
            count=len(open_alerts),
            aclass=str(a0.get("alert_class") or "signal"),
            summary=(str(a0.get("message_summary") or "")[:220]),
        )
        today_action = True
    elif kind != "closed_research_fixture":
        today_title = t(lg, "today.loadout")
        ev = brief["evidence_state_plain"] or t(lg, "today.evidence_fallback_short")
        today_body = (
            f"{brief['object_kind_label']}: {brief['one_line_explanation'][:400]}\n\n"
            f"{t(lg, 'today.stance_label')}: {brief['stance_plain']}. {t(lg, 'today.evidence_label')}: {ev}"
        )
        af = str(brief.get("action_framing") or "").lower()
        today_action = "no action" not in af and "조치 없음" not in af
    else:
        today_title = t(lg, "today.no_opportunity")
        today_body = t(lg, "today.body.fixture")
        today_action = False

    today_spectrum_summary = build_today_spectrum_summary_for_home(repo_root=repo_root, lang=lg)
    seed_spectrum_asset_ids = list_spectrum_seed_asset_ids(repo_root)
    seed_id_set = set(seed_spectrum_asset_ids)
    alias_map = load_spectrum_watch_alias_map(repo_root)

    watch_items: list[dict[str, Any]] = []
    sym = rm.get("cohort_symbols") or []
    watch_filter_ids = merge_watchlist_display_order(
        bundle_watch_candidate_asset_ids(bundle),
        load_watchlist_order(repo_root),
    )
    watch_spectrum_filter_ids = expand_watchlist_for_spectrum_filter(watch_filter_ids, alias_map)
    expanded_watch_set = set(watch_spectrum_filter_ids)
    watch_on_spectrum_raw = sorted(set(watch_filter_ids) & seed_id_set)
    watch_on_spectrum_aliased = sorted(expanded_watch_set & seed_id_set)
    sym_lab = t(lg, "watch.symbols_label")
    if sym:
        watch_items.append(
            {
                "label": str(rm.get("asset_id") or "Cohort"),
                "detail": f"{sym_lab}: {', '.join(str(s) for s in sym[:16])}",
                "why_watching": t(lg, "watch.why_cohort"),
            }
        )
    else:
        watch_items.append(
            {
                "label": str(rm.get("asset_id") or "Primary object"),
                "detail": brief["stance_plain"],
                "why_watching": t(lg, "watch.why_single"),
            }
        )

    jobs = _load_recent_jobs(repo_root)
    research_lines: list[dict[str, Any]] = []
    for j in jobs:
        st = str(j.get("status") or "")
        research_lines.append(
            {
                "headline": f"{j.get('job_type', '')} · {st}",
                "sub": j.get("result_summary") or t(lg, "research.sub_default"),
                "when": j.get("created_at") or "",
                "checkpoint": t(lg, "research.checkpoint"),
            }
        )

    alert_preview = []
    for a in (open_alerts[:4] + [x for x in alerts if x not in open_alerts][:2])[:5]:
        alert_preview.append(
            {
                "status": str(a.get("status") or ""),
                "class": str(a.get("alert_class") or ""),
                "asset_id": str(a.get("asset_id") or ""),
                "summary": str(a.get("message_summary") or "")[:200],
                "needs_attention": bool(a.get("requires_attention")),
            }
        )

    journal_preview = []
    for d in recent_decs:
        journal_preview.append(
            {
                "timestamp": str(d.get("timestamp") or "")[:19],
                "asset_id": str(d.get("asset_id") or ""),
                "decision_type": str(d.get("decision_type") or ""),
                "action_framing_plain": translate_token(str(d.get("decision_type") or ""), lang=lg),
                "why_short": str(d.get("founder_note") or "")[:220],
                "linked_message_summary": str(d.get("linked_message_summary") or "")[:220],
                "message_snapshot_id": str(d.get("message_snapshot_id") or ""),
                "replay_lineage_pointer": str(d.get("replay_lineage_pointer") or ""),
                "replay_hint": t(lg, "journal.replay_hint"),
            }
        )

    wc = rm.get("what_changed") or []
    copilot_daily = (
        f"{brief['action_framing']}. "
        f"{t(lg, 'copilot.has_alerts' if open_alerts else 'copilot.no_alerts')}"
    )

    fdp = load_frozen_snapshot_pack_v0(repo_root, lang=lg)

    empty_watch = {
        "title": t(lg, "watch.empty_title"),
        "why": t(lg, "watch.empty_why"),
        "fills_when": t(lg, "watch.empty_when"),
    }
    empty_research = {
        "title": t(lg, "research.empty_title"),
        "why": t(lg, "research.empty_why"),
        "fills_when": t(lg, "research.empty_when"),
    }
    empty_journal = {
        "title": t(lg, "journal.empty_title"),
        "why": t(lg, "journal.empty_why"),
        "fills_when": t(lg, "journal.empty_when"),
    }

    # Replay preview on Home (signature feature — compact, not the full timeline).
    wc0 = str(wc[0]) if wc else ""
    if recent_decs:
        d0 = recent_decs[0]
        replay_preview = {
            "headline": t(lg, "replay.preview.head.decision"),
            "asset_id": str(d0.get("asset_id") or ""),
            "timestamp": str(d0.get("timestamp") or "")[:19],
            "one_line": str(d0.get("why_short") or d0.get("action_framing_plain") or "")[:200],
            "time_axis_snippet": t(lg, "replay.preview.axis"),
            "since_then": wc0 or t(lg, "journal.replay_hint"),
            "opens_panel": "replay",
        }
        replay_preview_empty = None
    else:
        replay_preview = {
            "headline": t(lg, "replay.preview.head.default"),
            "asset_id": "",
            "timestamp": "",
            "one_line": t(lg, "replay.preview.no_decision"),
            "time_axis_snippet": t(lg, "replay.preview.axis"),
            "since_then": wc0 or str(brief.get("one_line_explanation") or "")[:220],
            "opens_panel": "replay",
        }
        replay_preview_empty = {
            "title": t(lg, "replay.preview.empty_title"),
            "why": t(lg, "replay.preview.empty_why"),
            "fills_when": t(lg, "replay.preview.empty_when"),
        }

    return {
        "ok": True,
        "lang": lg,
        "shell_version": "phase47e",
        "today": {
            "title": today_title,
            "body": today_body,
            "action_needed": today_action,
            "object_kind": kind,
        },
        "today_spectrum_summary": today_spectrum_summary,
        "today_spectrum_ui": {
            "watchlist_asset_ids": watch_filter_ids,
            "watchlist_spectrum_filter_ids": watch_spectrum_filter_ids,
            "spectrum_seed_asset_ids": seed_spectrum_asset_ids,
            "watchlist_on_spectrum": watch_on_spectrum_raw,
            "watchlist_on_spectrum_aliased": watch_on_spectrum_aliased,
        },
        "watchlist_block": {
            "items": watch_items,
            "what_changed_bullets": [str(x) for x in wc[:6]],
            "empty_state": empty_watch if not sym else None,
            "reorderable_asset_ids": list(watch_filter_ids),
        },
        "research_in_progress": {
            "threads": research_lines,
            "empty_state": empty_research if not research_lines else None,
        },
        "alerts_preview": alert_preview,
        "alerts_empty": {
            "title": t(lg, "alerts.empty_title"),
            "why": t(lg, "alerts.empty_why"),
            "fills_when": t(lg, "alerts.empty_when"),
        },
        "decision_journal_preview": journal_preview,
        "decision_journal_empty": empty_journal if not journal_preview else None,
        "ask_ai_brief": {
            "daily_line": copilot_daily,
            "shortcuts": ask_ai_brief_contract_localized(lg),
        },
        "portfolio_snapshot": {
            "state": "stub",
            "copy": t(lg, "portfolio.stub"),
        },
        "replay_preview": replay_preview,
        "replay_preview_empty": replay_preview_empty,
        "frozen_demo_pack": fdp if fdp.get("ok") else None,
        "closed_context": {
            "is_fixture": kind == "closed_research_fixture",
            "research_tab_note": t(lg, "closed.research_tab_note"),
        },
    }


def phase47d_bundle_core(*, design_source_path: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "ok": True,
        "phase": "phase47d_thick_slice_ux_shell_reset",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_source_path": design_source_path,
        "home_blocks": HOME_BLOCKS_CATALOG,
        "navigation_shell": SHELL_NAVIGATION_47D,
        "closed_fixture_repositioning": CLOSED_FIXTURE_REPOSITIONING,
        "ask_ai_brief_contract": ask_ai_brief_contract(),
        "replay_preview_contract": replay_preview_contract(),
        "empty_state_rules_applied": EMPTY_STATE_RULES_APPLIED,
        "phase47e": {
            "phase47e_recommendation": "live_watchlist_multi_asset_and_portfolio_attribution_v1",
            "focus": "Multi-row watchlist, live symbol hooks (still governed), portfolio card data — no substrate repair.",
        },
        "phase47f": phase47f_recommend(),
    }
