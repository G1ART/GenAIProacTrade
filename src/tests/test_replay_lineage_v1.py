"""Patch Bundle C — replay lineage pointer, message snapshot id, decision ledger join."""

from __future__ import annotations

import json
from pathlib import Path

from phase46.decision_trace_ledger import append_decision, list_decisions
from phase47_runtime.traceability_replay import api_replay_timeline_payload, build_timeline_events, micro_brief_for_event
from metis_brain.replay_lineage_v1 import message_snapshot_id_v1


def test_message_snapshot_id_stable() -> None:
    a = message_snapshot_id_v1(
        message_id="m1",
        registry_entry_id="reg1",
        artifact_id="art1",
        horizon="short",
        asset_id="A",
        as_of_utc="2026-01-01T00:00:00+00:00",
    )
    b = message_snapshot_id_v1(
        message_id="m1",
        registry_entry_id="reg1",
        artifact_id="art1",
        horizon="short",
        asset_id="A",
        as_of_utc="2026-01-01T00:00:00+00:00",
    )
    assert a == b and a.startswith("msg_snap:v1:")


def test_append_decision_optional_lineage_fields(tmp_path: Path) -> None:
    p = tmp_path / "d.json"
    append_decision(
        p,
        asset_id="DEMO_KR_A",
        decision_type="watch",
        founder_note="n",
        linked_message_summary="s",
        linked_authoritative_artifact="a",
        linked_research_provenance="p",
        replay_lineage_pointer="lineage:registry:short:demo_v0",
        message_snapshot_id="msg_snap:v1:abc",
        linked_registry_entry_id="reg_short_demo_v0",
        linked_artifact_id="art_short_demo_v0",
    )
    rows = list_decisions(p)
    assert len(rows) == 1
    d0 = rows[0]
    assert d0.get("replay_lineage_pointer") == "lineage:registry:short:demo_v0"
    assert d0.get("message_snapshot_id") == "msg_snap:v1:abc"
    assert d0.get("linked_registry_entry_id") == "reg_short_demo_v0"


def test_timeline_decision_event_carries_lineage(tmp_path: Path) -> None:
    b = {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-15T12:00:00+00:00",
        "founder_read_model": {"asset_id": "x", "current_stance": "hold", "what_changed": []},
        "cockpit_state": {},
    }
    dp = tmp_path / "dec.json"
    append_decision(
        dp,
        asset_id="x",
        decision_type="hold",
        founder_note="",
        linked_message_summary="m",
        linked_authoritative_artifact="art",
        linked_research_provenance="prov",
        replay_lineage_pointer="lin:1",
        message_snapshot_id="snap:1",
        linked_registry_entry_id="reg1",
        linked_artifact_id="art1",
    )
    decs = list_decisions(dp)
    events, err = build_timeline_events(bundle=b, decisions=decs, alerts=[])
    assert err is None
    de = next(e for e in events if e["event_type"] == "decision_event")
    assert de.get("replay_lineage_pointer") == "lin:1"
    assert de.get("message_snapshot_id") == "snap:1"
    assert de.get("linked_registry_entry_id") == "reg1"
    ap = tmp_path / "a.json"
    ap.write_text(json.dumps({"schema_version": 1, "alerts": []}), encoding="utf-8")
    tl = api_replay_timeline_payload(b, ap, dp)
    assert tl.get("replay_lineage_join_contract") == "REPLAY_LINEAGE_JOIN_V1"
    eid = de["event_id"]
    mb = micro_brief_for_event(tl["events"], eid)
    assert mb and mb.get("replay_lineage_pointer") == "lin:1"
    assert mb.get("message_snapshot_id") == "snap:1"
