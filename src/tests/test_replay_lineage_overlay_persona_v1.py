"""Pragmatic Brain Absorption v1 — Milestone E.

Replay lineage must carry overlay influence ids (from brain_overlays_v1) and
optionally persona candidate ids (PersonaCandidatePacketV1) so that future
reviewers can reconstruct *which non-quant adjustments and which candidate
hypotheses were in play* at decision time.

Q10 (message_snapshot_id + registry_entry_id simultaneously present) must
remain intact — these new fields are purely additive.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase46.decision_trace_ledger import (
    append_decision,
    decision_trace_ledger_schema,
    list_decisions,
)
from phase47_runtime.traceability_replay import (
    REPLAY_LINEAGE_OPTIONAL_FIELDS,
    _inject_lineage_into_timeline_events,
    build_timeline_events,
    micro_brief_for_event,
)


def test_optional_lineage_fields_include_overlay_and_persona():
    assert "brain_overlay_ids" in REPLAY_LINEAGE_OPTIONAL_FIELDS
    assert "persona_candidate_ids_at_decision" in REPLAY_LINEAGE_OPTIONAL_FIELDS


def test_decision_ledger_schema_documents_new_optional_lists():
    schema = decision_trace_ledger_schema()
    fields = schema["entry_fields"]
    assert "brain_overlay_ids_at_decision" in fields
    assert "persona_candidate_ids_at_decision" in fields
    assert "Candidate-only" in fields["persona_candidate_ids_at_decision"]


def test_append_decision_persists_overlay_and_persona_ids(tmp_path: Path):
    p = tmp_path / "d.json"
    append_decision(
        p,
        asset_id="DEMO_KR_A",
        decision_type="watch",
        founder_note="note",
        linked_message_summary="m",
        linked_authoritative_artifact="art",
        linked_research_provenance="prov",
        replay_lineage_pointer="lin:1",
        message_snapshot_id="snap:1",
        linked_registry_entry_id="reg_short_demo_v0",
        linked_artifact_id="art_short_demo_v0",
        brain_overlay_ids_at_decision=["ov_confidence_adj_accruals_short_v0"],
        persona_candidate_ids_at_decision=["pcand_demo_quant_v0"],
    )
    rows = list_decisions(p)
    assert rows[0]["brain_overlay_ids_at_decision"] == [
        "ov_confidence_adj_accruals_short_v0"
    ]
    assert rows[0]["persona_candidate_ids_at_decision"] == ["pcand_demo_quant_v0"]


def test_timeline_decision_event_carries_overlay_and_persona_ids(tmp_path: Path):
    b = {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-15T12:00:00+00:00",
        "founder_read_model": {
            "asset_id": "X",
            "current_stance": "hold",
            "what_changed": [],
        },
        "cockpit_state": {},
    }
    dp = tmp_path / "dec.json"
    append_decision(
        dp,
        asset_id="X",
        decision_type="hold",
        founder_note="",
        linked_message_summary="m",
        linked_authoritative_artifact="art",
        linked_research_provenance="prov",
        replay_lineage_pointer="lin:1",
        message_snapshot_id="snap:1",
        linked_registry_entry_id="reg1",
        linked_artifact_id="art1",
        brain_overlay_ids_at_decision=["ov_regime_shift_demo"],
        persona_candidate_ids_at_decision=["pcand_regime_demo"],
    )
    decs = list_decisions(dp)
    events, err = build_timeline_events(bundle=b, decisions=decs, alerts=[])
    assert err is None
    de = next(e for e in events if e["event_type"] == "decision_event")
    assert de["brain_overlay_ids_at_decision"] == ["ov_regime_shift_demo"]
    assert de["persona_candidate_ids_at_decision"] == ["pcand_regime_demo"]


def test_lineage_injection_propagates_overlay_ids_from_registry_surface():
    """When replay join carries brain_overlay_ids (from the registry surface),
    same-asset events should pick them up without overwriting decision-level
    lists already on the event."""
    events = [
        {
            "event_id": "evt1",
            "asset_id": "X",
            "event_type": "research_event",
        },
        {
            "event_id": "evt2",
            "asset_id": "X",
            "event_type": "decision_event",
            "brain_overlay_ids": ["already_present_override"],
        },
        {
            "event_id": "evt3",
            "asset_id": "Y",
            "event_type": "research_event",
        },
    ]
    join = {
        "contract": "REPLAY_LINEAGE_JOIN_V1",
        "asset_id": "X",
        "brain_overlay_ids": ["ov_from_registry_surface"],
    }
    registry_surface = {
        "contract": "TODAY_REGISTRY_SURFACE_V1",
        "brain_overlay_ids": ["ov_from_registry_surface"],
    }
    _inject_lineage_into_timeline_events(events, join, registry_surface)
    assert events[0]["brain_overlay_ids"] == ["ov_from_registry_surface"]
    # Pre-existing decision-level overlays are preserved (not overwritten).
    assert events[1]["brain_overlay_ids"] == ["already_present_override"]
    assert "brain_overlay_ids" not in events[2]


def test_micro_brief_surfaces_overlay_and_persona_list_fields():
    event = {
        "event_id": "evt",
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "event_type": "decision_event",
        "asset_id": "X",
        "title": "Decision: watch",
        "stance_at_time": "watch",
        "message_summary": "",
        "evidence_summary": "",
        "founder_note": "",
        "known_then": "",
        "brain_overlay_ids": ["ov_a", "ov_b"],
        "brain_overlay_ids_at_decision": ["ov_a"],
        "persona_candidate_ids_at_decision": ["pcand_a"],
    }
    mb = micro_brief_for_event([event], "evt")
    assert mb is not None
    assert mb["brain_overlay_ids"] == ["ov_a", "ov_b"]
    assert mb["brain_overlay_ids_at_decision"] == ["ov_a"]
    assert mb["persona_candidate_ids_at_decision"] == ["pcand_a"]


def test_q10_contract_preserved_in_message_snapshot_store():
    """Q10 must continue to pass: every persisted snapshot should still be
    able to produce message_snapshot_id + registry_entry_id pairs. The
    Milestone E additions are purely additive — no field renames, no
    required-field removals."""
    store_path = Path(__file__).resolve().parents[2] / "data" / "mvp" / "message_snapshots_v0.json"
    assert store_path.is_file(), f"message snapshot store missing: {store_path}"
    raw = json.loads(store_path.read_text(encoding="utf-8"))
    snaps = raw.get("snapshots") or {}
    assert isinstance(snaps, dict) and snaps, "no snapshots persisted"
    got_pair = False
    for sid, rec in snaps.items():
        if not isinstance(rec, dict):
            continue
        if str(sid).strip() and str(rec.get("registry_entry_id") or "").strip():
            got_pair = True
            break
    assert got_pair, "no snapshot carries both message_snapshot_id and registry_entry_id"
