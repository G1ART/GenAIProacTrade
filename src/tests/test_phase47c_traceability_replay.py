"""Phase 47c: replay timeline, micro-brief, mode separation, no future-leak labels."""

from __future__ import annotations

import json
from pathlib import Path

from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.traceability_replay import (
    EVENT_GRAMMAR,
    REPLAY_RULES,
    api_replay_timeline_payload,
    build_counterfactual_scaffold,
    build_timeline_events,
    micro_brief_for_event,
    phase47c_bundle_core,
    replay_labels_have_no_future_leakage,
)


def _minimal_bundle() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-15T12:00:00+00:00",
        "founder_read_model": {
            "asset_id": "t1",
            "current_stance": "hold",
            "what_changed": ["evidence tick"],
            "decision_card": {"title": "T", "body": "body at bundle time"},
        },
        "cockpit_state": {"cohort_aggregate": {}},
    }


def test_timeline_merges_bundle_decisions_alerts(tmp_path: Path) -> None:
    b = _minimal_bundle()
    ap = tmp_path / "alerts.json"
    dp = tmp_path / "dec.json"
    ap.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "alerts": [
                    {
                        "alert_id": "a1",
                        "alert_timestamp": "2026-01-10T00:00:00+00:00",
                        "asset_id": "t1",
                        "alert_class": "signal",
                        "message_summary": "hello",
                        "triggering_source_artifact": "x",
                        "requires_attention": True,
                        "status": "open",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    dp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decisions": [
                    {
                        "timestamp": "2026-01-12T00:00:00+00:00",
                        "asset_id": "t1",
                        "decision_type": "hold",
                        "founder_note": "steady",
                        "linked_message_summary": "lm",
                        "linked_authoritative_artifact": "art",
                        "linked_research_provenance": "prov",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    decs = json.loads(dp.read_text())["decisions"]
    alerts = json.loads(ap.read_text())["alerts"]
    events, err = build_timeline_events(bundle=b, decisions=decs, alerts=alerts)
    assert err is None
    types = [e["event_type"] for e in events]
    assert "research_event" in types
    assert "ai_message_event" in types
    assert "decision_event" in types
    assert "outcome_checkpoint" in types
    assert replay_labels_have_no_future_leakage(events)
    for e in events:
        assert "asset_id" in e
    assert next(e for e in events if e["event_id"] == "evt_bundle_authoritative").get("asset_id") == "t1"
    assert next(e for e in events if e["event_type"] == "decision_event").get("asset_id") == "t1"
    assert next(e for e in events if e["event_type"] == "ai_message_event").get("asset_id") == "t1"
    de = next(e for e in events if e["event_type"] == "decision_event")
    assert "replay_lineage_pointer" in de and "message_snapshot_id" in de


def test_micro_brief_includes_style_and_framing() -> None:
    b = _minimal_bundle()
    events, _ = build_timeline_events(bundle=b, decisions=[], alerts=[])
    eid = events[0]["event_id"]
    mb = micro_brief_for_event(events, eid)
    assert mb and mb.get("style_token")
    assert mb.get("asset_id") == "t1"
    assert "decision_quality_note" in mb
    assert "outcome_quality_note" in mb


def test_counterfactual_scaffold_separate_from_replay_rules() -> None:
    cf = build_counterfactual_scaffold()
    assert cf.get("mode") == "counterfactual_lab"
    rules_blob = " ".join(cf.get("rules") or []).lower()
    assert "counterfactual" in rules_blob
    disc = str(cf.get("disclaimer") or "").lower()
    assert "hypothetical" in disc
    assert any("no counterfactual" in r.lower() for r in REPLAY_RULES)


def test_event_grammar_maps_known_types() -> None:
    types = {x["type"] for x in EVENT_GRAMMAR}
    for t in ("research_event", "decision_event", "ai_message_event", "outcome_checkpoint"):
        assert t in types


def test_phase47c_bundle_core_shape() -> None:
    core = phase47c_bundle_core(design_paths=["docs/DESIGN.md"])
    assert core["ok"] and core["phase"] == "phase47c_traceability_replay"
    for k in (
        "traceability_views",
        "plot_grammar",
        "event_grammar",
        "replay_rules",
        "counterfactual_rules",
        "counterfactual_scaffold",
        "phase47d",
    ):
        assert k in core


def test_api_timeline_portfolio_stub() -> None:
    b = _minimal_bundle()
    p = Path("/tmp/__nonexistent_alert__.json")
    out = api_replay_timeline_payload(b, p, p)
    assert out["ok"]
    assert out.get("portfolio_traceability", {}).get("state") == "stub"


def test_dispatch_replay_endpoints(tmp_path: Path) -> None:
    bpath = tmp_path / "b46.json"
    bpath.write_text(json.dumps(_minimal_bundle()), encoding="utf-8")
    ap = tmp_path / "alerts.json"
    dp = tmp_path / "dec.json"
    ap.write_text(json.dumps({"schema_version": 1, "alerts": []}), encoding="utf-8")
    dp.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)

    code, obj = dispatch_json(st, method="GET", path="/api/replay/timeline", body=None)
    assert code == 200
    assert obj.get("ok") and obj.get("mode") == "replay"
    ev0 = (obj.get("events") or [{}])[0]
    eid = ev0.get("event_id")

    code2, obj2 = dispatch_json(
        st,
        method="GET",
        path="/api/replay/micro-brief",
        body=None,
        query={"event_id": eid},
    )
    assert code2 == 200
    assert obj2.get("ok") and obj2.get("micro_brief", {}).get("event_id") == eid

    code3, obj3 = dispatch_json(st, method="GET", path="/api/replay/contract", body=None)
    assert code3 == 200
    assert obj3.get("traceability_views")


def test_invalid_bundle_timeline_422(tmp_path: Path) -> None:
    bad = {"ok": True, "generated_utc": "not-a-date", "founder_read_model": {}}
    bpath = tmp_path / "bad.json"
    bpath.write_text(json.dumps(bad), encoding="utf-8")
    ap = tmp_path / "a.json"
    dp = tmp_path / "d.json"
    ap.write_text(json.dumps({"schema_version": 1, "alerts": []}), encoding="utf-8")
    dp.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    code, obj = dispatch_json(st, method="GET", path="/api/replay/timeline", body=None)
    assert code == 422
    assert not obj.get("ok")


def test_sanitize_removes_future_phrase() -> None:
    b = _minimal_bundle()
    b["founder_read_model"]["decision_card"] = {
        "body": "We will be rich if this works",
    }
    events, _ = build_timeline_events(bundle=b, decisions=[], alerts=[])
    assert replay_labels_have_no_future_leakage(events)
    blob = json.dumps(events, ensure_ascii=False).lower()
    assert "will be" not in blob or "redacted" in blob
