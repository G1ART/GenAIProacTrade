"""Phase 47b: user-first copy, navigation contract, surface API, bundle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase47_runtime.phase47b_orchestrator import run_phase47b_user_first_ux
from phase47_runtime.routes import api_overview, api_user_first_section, dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.ui_copy import (
    FORBIDDEN_LEGACY_OPTIMISTIC_TOKENS,
    build_section_payload,
    build_user_first_brief,
    governed_prompt_shortcuts,
    infer_object_kind,
    navigation_contract,
    translate_token,
)


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


def test_translate_token_known() -> None:
    assert "limited" in translate_token("deferred_due_to_proxy_limited_falsifier_substrate").lower()


def test_infer_object_kind_fixture() -> None:
    b = _minimal_phase46_bundle()
    assert infer_object_kind(b) == "closed_research_fixture"


def test_build_user_first_brief_action_framing() -> None:
    b = _minimal_phase46_bundle()
    bf = build_user_first_brief(b)
    assert bf["object_kind"] == "closed_research_fixture"
    assert bf["action_framing"]
    blob = json.dumps(bf, ensure_ascii=False).lower()
    for bad in FORBIDDEN_LEGACY_OPTIMISTIC_TOKENS:
        assert bad not in blob


def test_navigation_contract_shape() -> None:
    nav = navigation_contract()
    assert "primary_navigation" in nav
    assert "object_detail_sections" in nav
    pids = [x["id"] for x in nav["primary_navigation"]]
    assert "home" in pids
    assert "journal" in pids
    assert "advanced" in pids
    ids = [x["id"] for x in nav["object_detail_sections"]]
    assert ids[:3] == ["brief", "why_now", "what_could_change"]
    assert "advanced" in ids


def test_governed_shortcuts_cover_design() -> None:
    labels = {x["label"].lower() for x in governed_prompt_shortcuts()}
    assert "explain this briefly" in labels
    assert "log" not in labels


def test_build_section_payload_advanced_has_raw(tmp_path: Path) -> None:
    b = _minimal_phase46_bundle()
    adv = build_section_payload(b, "advanced")
    assert "raw_drilldown" in adv
    assert "decision" in adv["raw_drilldown"]


def test_api_user_first_section_dispatch(tmp_path: Path) -> None:
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    bundle = _minimal_phase46_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    ov = api_overview(st)
    assert "user_first" in ov
    assert ov["user_first"]["brief"]["object_kind"] == "closed_research_fixture"

    code, obj = dispatch_json(st, method="GET", path="/api/user-first/section/brief", body=None)
    assert code == 200 and obj.get("ok") is True
    assert obj.get("paragraphs")

    code, bad = dispatch_json(st, method="GET", path="/api/user-first/section/unknown", body=None)
    assert code == 404


def test_phase47b_orchestrator_bundle_fields(tmp_path: Path) -> None:
    design = tmp_path / "DESIGN.md"
    design.write_text("# DESIGN\n", encoding="utf-8")
    out = run_phase47b_user_first_ux(design_source_path=str(design), repo_root=tmp_path)
    assert out["ok"] is True
    assert out["phase"] == "phase47b_user_first_ux"
    for k in (
        "generated_utc",
        "design_source_path",
        "primary_navigation",
        "object_hierarchy",
        "status_translation_examples",
        "action_framing_examples",
        "advanced_boundary_rules",
        "phase47c",
    ):
        assert k in out
    assert out["phase47c"].get("phase47c_recommendation")


def test_repo_phase46_user_first_no_forbidden_tokens() -> None:
    repo = Path(__file__).resolve().parents[2]
    p46 = repo / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    if not p46.is_file():
        pytest.skip("phase46 bundle missing")
    b = json.loads(p46.read_text(encoding="utf-8"))
    bf = build_user_first_brief(b)
    text = json.dumps(bf, ensure_ascii=False).lower()
    for bad in FORBIDDEN_LEGACY_OPTIMISTIC_TOKENS:
        assert bad not in text
