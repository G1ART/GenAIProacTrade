"""Phase 47d: Home feed API, shell nav, copilot brief contract, bundle."""

from __future__ import annotations

import json
from pathlib import Path

from phase47_runtime.home_feed import (
    HOME_BLOCKS_CATALOG,
    SHELL_NAVIGATION_47D,
    ask_ai_brief_contract,
    build_home_feed_payload,
    phase47d_bundle_core,
)
from phase47_runtime.phase47d_orchestrator import run_phase47d_thick_slice_home_feed
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.ui_copy import build_section_payload, navigation_contract


def _minimal_phase46_bundle() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {
            "asset_id": "research_engine_fixture_cohort_x",
            "headline_message": "Closed under narrow claims.",
            "current_stance": "hold_closeout_until_named_new_source_or_new_evidence_v1",
            "closeout_status": "closed_pending_new_evidence",
            "reopen_requires_named_source": True,
            "what_changed": ["Diagnostic label refined."],
            "what_did_not_change": ["Gate unchanged."],
            "current_uncertainties": ["Sector still unavailable."],
            "next_watchpoints": ["Named source distinct from prior path."],
            "gate_summary": {
                "gate_status": "deferred",
                "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
            },
            "trace_links": {"p44": "/tmp/x.json"},
        },
        "cockpit_state": {
            "cohort_aggregate": {
                "founder_primary_status": "watching_for_new_evidence",
                "decision_card": {"title": "Stance", "body": "Hold until new evidence."},
                "message_card": {"title": "Msg", "body": "Fixture message."},
                "information_card": {"title": "Facts", "bullets": ["8-row fixture."]},
                "research_provenance_card": {"title": "Prov", "bullets": ["Phase 44 authoritative."]},
                "closeout_reopen_card": {
                    "title": "Reopen",
                    "closeout": "closed_pending_new_evidence",
                    "reopen_note": "Register named source first.",
                },
            }
        },
        "representative_pitch": {"top_level_pitch": "pitch", "layer_summaries": {"decision": "d"}},
        "drilldown_examples": {
            layer: {"layer": layer, "summary": f"s-{layer}", "structured": {"k": 1}, "governed": True}
            for layer in ("decision", "message", "information", "research", "provenance", "closeout")
        },
    }


def _runtime(tmp_path: Path) -> CockpitRuntimeState:
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    bundle = _minimal_phase46_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


def test_navigation_shell_matches_primary_nav() -> None:
    nav = navigation_contract()
    pnav = nav["primary_navigation"]
    assert len(pnav) == len(SHELL_NAVIGATION_47D)
    assert [x["id"] for x in pnav] == [x["id"] for x in SHELL_NAVIGATION_47D]


def test_home_blocks_catalog_covers_workorder() -> None:
    ids = {b["id"] for b in HOME_BLOCKS_CATALOG}
    for need in (
        "today",
        "watchlist",
        "research_in_progress",
        "alerts",
        "decision_journal",
        "ask_ai_brief",
        "portfolio_snapshot",
    ):
        assert need in ids


def test_ask_ai_brief_contract_includes_replay_panel_hint() -> None:
    rows = ask_ai_brief_contract()
    labels = [r["label"] for r in rows]
    assert "What matters now?" in labels
    assert "Open Replay for this item" in labels
    replay = next(x for x in rows if x.get("id") == "open_replay")
    assert replay.get("opens_panel") == "replay"


def test_build_home_feed_closed_fixture_today_is_plain_text(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    payload = build_home_feed_payload(st)
    assert payload["ok"] is True
    body = payload["today"]["body"]
    assert isinstance(body, str)
    low = body.lower()
    assert "closed" in low or "archive" in low or "replay" in low
    assert payload["closed_context"]["is_fixture"] is True


def test_build_home_feed_journal_empty_state(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    payload = build_home_feed_payload(st)
    assert payload["decision_journal_empty"] is not None
    es = payload["decision_journal_empty"]
    assert "title" in es and "why" in es and "fills_when" in es


def test_history_section_links_journal_and_advanced() -> None:
    b = _minimal_phase46_bundle()
    hist = build_section_payload(b, "history")
    panels = [x["panel"] for x in (hist.get("links") or [])]
    assert "journal" in panels
    assert "advanced" in panels


def test_dispatch_home_feed_ok(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, obj = dispatch_json(st, method="GET", path="/api/home/feed", body=None)
    assert code == 200 and obj.get("ok") is True
    assert "today" in obj and "watchlist_block" in obj
    assert isinstance(obj["today"].get("body"), str)


def test_phase47d_orchestrator_required_fields(tmp_path: Path) -> None:
    design = tmp_path / "DESIGN_V3.md"
    design.write_text("# V3\n", encoding="utf-8")
    out = run_phase47d_thick_slice_home_feed(design_source_path=str(design), repo_root=tmp_path)
    for k in (
        "ok",
        "phase",
        "generated_utc",
        "design_source_path",
        "home_blocks",
        "navigation_shell",
        "closed_fixture_repositioning",
        "ask_ai_brief_contract",
        "empty_state_rules_applied",
        "phase47e",
    ):
        assert k in out
    assert out["phase47e"].get("phase47e_recommendation")


def test_phase47d_bundle_core_static_shape() -> None:
    core = phase47d_bundle_core(design_source_path="docs/DESIGN_V3_MINIMAL_AND_STRONG.md")
    assert core["navigation_shell"][0]["id"] == "home"
