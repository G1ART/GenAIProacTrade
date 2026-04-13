"""Phase 47: runtime state, API routes, governed conversation, ledger writes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase46.alert_ledger import append_alert, list_alerts, update_alert_status
from phase46.decision_trace_ledger import append_decision, list_decisions
from phase46.orchestrator import run_phase46_founder_decision_cockpit
from phase47_runtime.governed_conversation import process_governed_prompt
from phase47_runtime.notification_hooks import clear_notifications_for_tests, list_notifications
from phase47_runtime.orchestrator import run_phase47_founder_cockpit_runtime
from phase47_runtime.routes import (
    api_alert_action,
    api_conversation,
    api_decision_append,
    api_drilldown,
    api_meta,
    api_overview,
    api_reload,
    dispatch_json,
)
from phase47_runtime.runtime_state import CockpitRuntimeState

_FORBIDDEN = (
    "continue_bounded_falsifier_retest_or_narrow_claims_v1",
    "substrate_backfill_or_narrow_claims_then_retest_v1",
)


def _minimal_phase46_bundle() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {
            "asset_id": "test_cohort",
            "what_changed": ["a"],
            "what_did_not_change": ["b"],
            "trace_links": {"p45": "x"},
            "current_stance": "hold",
            "authoritative_recommendation": "narrow",
        },
        "cockpit_state": {
            "cohort_aggregate": {
                "founder_primary_status": "watching_for_new_evidence",
                "decision_card": {"title": "D", "body": "decision body"},
                "message_card": {"title": "M", "body": "msg"},
                "information_card": {"title": "I", "bullets": ["u1"]},
                "research_provenance_card": {"title": "R", "bullets": ["r1"]},
                "closeout_reopen_card": {"title": "C", "closeout": "closed"},
            }
        },
        "representative_pitch": {
            "top_level_pitch": "pitch",
            "why_this_matters": "why",
            "what_remains_unproven": "unproven",
            "layer_summaries": {"decision": "ld", "message": "lm", "information": "li", "research": "lr", "provenance": "lp", "closeout": "lc"},
        },
        "drilldown_examples": {
            layer: {
                "layer": layer,
                "summary": f"summary-{layer}",
                "structured": {},
                "governed": True,
            }
            for layer in ("decision", "message", "information", "research", "provenance", "closeout")
        },
    }


def test_runtime_state_reload_and_stale(tmp_path: Path) -> None:
    bpath = tmp_path / "b46.json"
    bpath.write_text(json.dumps(_minimal_phase46_bundle()), encoding="utf-8")
    ap = tmp_path / "alerts.json"
    dp = tmp_path / "dec.json"
    ap.write_text(json.dumps({"schema_version": 1, "alerts": []}), encoding="utf-8")
    dp.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    bundle = _minimal_phase46_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")

    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    assert st.bundle["phase"] == "phase46_founder_decision_cockpit"
    assert api_meta(st)["bundle_ok"] is True
    assert st.is_bundle_stale() is False
    import time

    time.sleep(0.05)
    bpath.write_text(json.dumps({**bundle, "generated_utc": "2026-01-02T00:00:00+00:00"}), encoding="utf-8")
    assert st.is_bundle_stale() is True
    api_reload(st)
    assert st.is_bundle_stale() is False


def test_governed_conversation_intents() -> None:
    b = _minimal_phase46_bundle()
    for prompt, expect in [
        ("decision summary", "decision_summary"),
        ("information layer", "information_layer"),
        ("what changed", "what_changed"),
        ("why is this closed", "why_closed"),
        ("show provenance", "provenance"),
        ("what could change", "closeout_layer"),
    ]:
        r = process_governed_prompt(b, prompt)
        assert r["intent"] == expect
        blob = json.dumps(r, ensure_ascii=False)
        for bad in _FORBIDDEN:
            assert bad not in blob.lower()


def test_governed_conversation_outside_scope() -> None:
    r = process_governed_prompt(_minimal_phase46_bundle(), "buy everything now random")
    assert r["intent"] == "outside_governed_cockpit_scope"


@pytest.mark.parametrize(
    "action,expected",
    [
        ("acknowledge", "acknowledged"),
        ("resolve", "resolved"),
        ("supersede", "superseded"),
        ("dismiss", "dismissed"),
    ],
)
def test_alert_action_writes(tmp_path: Path, action: str, expected: str) -> None:
    clear_notifications_for_tests()
    ap = tmp_path / "a.json"
    append_alert(
        ap,
        asset_id="x",
        alert_class="t",
        message_summary="m",
        triggering_source_artifact="b",
        requires_attention=True,
    )
    alerts = list_alerts(ap)
    aid = alerts[0]["alert_id"]
    bpath = tmp_path / "b.json"
    bundle = _minimal_phase46_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(tmp_path / "d.json")
    (tmp_path / "d.json").write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    r = api_alert_action(st, {"action": action, "alert_id": aid})
    assert r["ok"] is True
    assert r["alert"]["status"] == expected
    ev = list_notifications()
    assert any(e.get("kind") == "alert_status_changed" for e in ev)


def test_decision_append_writes(tmp_path: Path) -> None:
    clear_notifications_for_tests()
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    bundle = _minimal_phase46_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    r = api_decision_append(
        st,
        {
            "decision_type": "hold",
            "asset_id": "test_cohort",
            "founder_note": "n",
            "linked_message_summary": "m",
            "linked_authoritative_artifact": "p46",
            "linked_research_provenance": "p44",
        },
    )
    assert r["ok"] is True
    assert len(list_decisions(dp)) == 1
    assert any(e.get("kind") == "decision_recorded" for e in list_notifications())


def test_dispatch_http_shapes(tmp_path: Path) -> None:
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
    code, obj = dispatch_json(st, method="GET", path="/api/meta", body=None)
    assert code == 200 and obj.get("ok", True)

    code, obj = dispatch_json(
        st,
        method="GET",
        path="/api/alerts",
        body=None,
        query={"status": "open"},
    )
    assert code == 200

    code, obj = dispatch_json(
        st,
        method="POST",
        path="/api/conversation",
        body=json.dumps({"text": "research layer"}).encode(),
    )
    assert code == 200
    assert obj["response"]["intent"] == "research_layer"


def test_phase47_orchestrator_bundle_fields() -> None:
    repo = Path(__file__).resolve().parents[2]
    p46 = repo / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    if not p46.is_file():
        pytest.skip("phase46 bundle missing")
    out = run_phase47_founder_cockpit_runtime(phase46_bundle_in=str(p46))
    assert out["ok"] is True
    assert out["phase"] == "phase47_founder_cockpit_runtime"
    for k in (
        "generated_utc",
        "input_phase46_bundle_path",
        "runtime_entrypoint",
        "runtime_views",
        "governed_conversation_contract",
        "alert_actions_supported",
        "decision_actions_supported",
        "reload_model",
        "deploy_target",
        "phase48",
    ):
        assert k in out


def test_operator_phase46_smoke_for_overview_sections(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p45p = repo / "docs/operator_closeout/phase45_canonical_closeout_bundle.json"
    p44p = repo / "docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json"
    if not p45p.is_file() or not p44p.is_file():
        pytest.skip("operator bundles missing")
    p45c = tmp_path / "p45.json"
    p44c = tmp_path / "p44.json"
    p45c.write_text(p45p.read_text(encoding="utf-8"), encoding="utf-8")
    p44c.write_text(p44p.read_text(encoding="utf-8"), encoding="utf-8")
    out = run_phase46_founder_decision_cockpit(
        phase45_bundle_in=str(p45c),
        phase44_bundle_in=str(p44c),
        repo_root=tmp_path,
    )
    bpath = tmp_path / "phase46.json"
    bpath.write_text(json.dumps(out), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    ov = api_overview(st)
    assert ov.get("asset_id")
    assert ov.get("pitch_summary")
    assert ov.get("decision_card")
    assert "counts" in ov
    for layer in ("decision", "provenance", "closeout"):
        d = api_drilldown(st, layer)
        assert d["ok"] and d["content"].get("governed") is True
    r = process_governed_prompt(st.bundle, "what remains unproven")
    blob = json.dumps(r, ensure_ascii=False)
    for bad in _FORBIDDEN:
        assert bad not in blob.lower()


def test_update_alert_status_by_index(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    append_alert(
        p,
        asset_id="a",
        alert_class="c",
        message_summary="m",
        triggering_source_artifact="t",
        requires_attention=False,
    )
    update_alert_status(p, new_status="acknowledged", index=0)
    assert list_alerts(p)[0]["status"] == "acknowledged"
