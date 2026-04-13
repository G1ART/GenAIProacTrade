"""Phase 47d — thick-slice Home feed blocks, shell nav contract, copilot brief (DESIGN_V3-aligned)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase46.alert_ledger import list_alerts
from phase46.decision_trace_ledger import list_decisions

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


def ask_ai_brief_contract() -> list[dict[str, str]]:
    """Premium copilot brief — shortcuts (label + governed prompt text)."""
    return [
        {"id": "matters_now", "label": "What matters now?", "prompt_text": "decision summary"},
        {"id": "what_changed", "label": "What changed?", "prompt_text": "what changed"},
        {"id": "active_research", "label": "Show my active research", "prompt_text": "research layer"},
        {"id": "review_next", "label": "What should I review next?", "prompt_text": "what remains unproven"},
        {"id": "last_decisions", "label": "Show my last decisions", "prompt_text": "decision summary"},
        {
            "id": "open_replay",
            "label": "Open Replay for this item",
            "prompt_text": "what changed",
            "opens_panel": "replay",
        },
    ]


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


def build_home_feed_payload(state: Any) -> dict[str, Any]:
    """Compose machine + human-readable Home blocks for API + static UI."""
    bundle = state.bundle
    repo_root = state.repo_root
    brief = build_user_first_brief(bundle)
    kind = infer_object_kind(bundle)
    rm = bundle.get("founder_read_model") or {}
    alerts = list_alerts(state.alert_ledger_path)
    decisions = list_decisions(state.decision_ledger_path)
    open_alerts = [a for a in alerts if str(a.get("status") or "") == "open"]
    recent_decs = list(reversed(decisions[-8:]))

    # Today — do not hero closed fixture without context
    if open_alerts:
        a0 = open_alerts[0]
        today_title = "Attention on your alerts"
        today_body = (
            f"You have {len(open_alerts)} open alert(s). The most recent: "
            f"{str(a0.get('alert_class') or 'signal')} — {(str(a0.get('message_summary') or '')[:220])}"
        )
        today_action = True
    elif kind != "closed_research_fixture":
        today_title = "Current loadout"
        today_body = (
            f"{brief['object_kind_label']}: {brief['one_line_explanation'][:400]}\n\n"
            f"Stance: {brief['stance_plain']}. Evidence: {brief['evidence_state_plain'] or 'See Research.'}"
        )
        af = str(brief.get("action_framing") or "").lower()
        today_action = "no action" not in af
    else:
        today_title = "No live opportunity in this loadout"
        today_body = (
            "The primary bundle is a **closed research record** — useful for audit and replay, "
            "not a headline buy/sell call. Check **Watchlist** for what you are tracking, "
            "**Research in progress** for runtime activity, and **Alerts** for new signals."
        )
        today_action = False

    watch_items: list[dict[str, Any]] = []
    sym = rm.get("cohort_symbols") or []
    if sym:
        watch_items.append(
            {
                "label": str(rm.get("asset_id") or "Cohort"),
                "detail": f"Symbols: {', '.join(str(s) for s in sym[:16])}",
                "why_watching": "Governed cohort in current bundle — stance reflects evidence limits, not hype.",
            }
        )
    else:
        watch_items.append(
            {
                "label": str(rm.get("asset_id") or "Primary object"),
                "detail": brief["stance_plain"],
                "why_watching": "Single-object loadout; add breadth via future watchlist ingest (Phase 51+).",
            }
        )

    jobs = _load_recent_jobs(repo_root)
    research_lines: list[dict[str, Any]] = []
    for j in jobs:
        st = str(j.get("status") or "")
        research_lines.append(
            {
                "headline": f"{j.get('job_type', '')} · {st}",
                "sub": j.get("result_summary") or "No summary yet.",
                "when": j.get("created_at") or "",
                "checkpoint": "Next: bundle reload or external trigger may enqueue a new bounded cycle.",
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
                "action_framing_plain": translate_token(str(d.get("decision_type") or "")),
                "why_short": str(d.get("founder_note") or "")[:220],
                "replay_hint": "Open Replay for the timeline around this decision.",
            }
        )

    wc = rm.get("what_changed") or []
    copilot_daily = (
        f"Now: {brief['action_framing']}. "
        f"{'Open items need review.' if open_alerts else 'No open alerts — scan Research activity or use a shortcut below.'}"
    )

    empty_watch = {
        "title": "Watchlist is thin",
        "why": "This build loads one authoritative cohort object; multi-name watchlists arrive via future ingest.",
        "fills_when": "Additional assets or external watch events are registered under governance.",
    }
    empty_research = {
        "title": "No recent job rows",
        "why": "The research job registry is empty or not yet populated on this machine.",
        "fills_when": "Phase 48/51 cycles run and write to `research_job_registry_v1.json`.",
    }
    empty_journal = {
        "title": "Journal is empty",
        "why": "No operator decisions have been logged in the decision trace ledger.",
        "fills_when": "You record a decision under Journal (or legacy path).",
    }

    return {
        "ok": True,
        "shell_version": "phase47d",
        "today": {
            "title": today_title,
            "body": today_body,
            "action_needed": today_action,
            "object_kind": kind,
        },
        "watchlist_block": {
            "items": watch_items,
            "what_changed_bullets": [str(x) for x in wc[:6]],
            "empty_state": empty_watch if not sym else None,
        },
        "research_in_progress": {
            "threads": research_lines,
            "empty_state": empty_research if not research_lines else None,
        },
        "alerts_preview": alert_preview,
        "alerts_empty": {
            "title": "No alerts",
            "why": "Nothing in the alert ledger matches the current surface.",
            "fills_when": "Runtime signals, reopen conditions, or Phase 48 outputs append to the ledger.",
        },
        "decision_journal_preview": journal_preview,
        "decision_journal_empty": empty_journal if not journal_preview else None,
        "ask_ai_brief": {
            "daily_line": copilot_daily,
            "shortcuts": ask_ai_brief_contract(),
        },
        "portfolio_snapshot": {
            "state": "stub",
            "copy": "Portfolio attribution and positions are not shown here yet — reserved for a later slice.",
        },
        "closed_context": {
            "is_fixture": kind == "closed_research_fixture",
            "research_tab_note": "Full cohort cards, evidence, and archive-style context live under Research.",
        },
    }


def phase47d_bundle_core(*, design_source_path: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "ok": True,
        "phase": "phase47d_thick_slice_home_feed",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_source_path": design_source_path,
        "home_blocks": HOME_BLOCKS_CATALOG,
        "navigation_shell": SHELL_NAVIGATION_47D,
        "closed_fixture_repositioning": CLOSED_FIXTURE_REPOSITIONING,
        "ask_ai_brief_contract": ask_ai_brief_contract(),
        "empty_state_rules_applied": EMPTY_STATE_RULES_APPLIED,
        "phase47e": {
            "phase47e_recommendation": "live_watchlist_multi_asset_and_portfolio_attribution_v1",
            "focus": "Multi-row watchlist, live symbol hooks (still governed), portfolio card data — no substrate repair.",
        },
    }
