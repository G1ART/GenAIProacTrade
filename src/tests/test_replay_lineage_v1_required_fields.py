"""Phase C3 — Replay lineage required fields on timeline events (registry_entry_id +
message_snapshot_id). Migration mode keeps legacy events; strict mode drops them.

Also exercises an end-to-end join: Today spectrum payload → persisted message snapshot →
replay timeline event carries matching ``message_snapshot_id``.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase47_runtime.traceability_replay import (
    REPLAY_LINEAGE_REQUIRED_FIELDS,
    audit_timeline_events_for_lineage,
    build_timeline_events,
    missing_required_lineage_fields,
)


def _empty_ledger_payload(kind: str) -> str:
    return json.dumps({"schema_version": 1, kind: []})


def _bundle(with_lineage: bool = False) -> dict:
    rm: dict = {
        "asset_id": "T1",
        "current_stance": "hold",
        "what_changed": ["tick"],
        "decision_card": {"title": "t", "body": "b"},
    }
    if with_lineage:
        rm["registry_entry_id"] = "reg_short_v1"
        rm["message_snapshot_id"] = "msg_snap_001"
    return {
        "ok": True,
        "generated_utc": "2026-04-01T12:00:00+00:00",
        "founder_read_model": rm,
        "cockpit_state": {"cohort_aggregate": {}},
    }


def test_required_fields_tuple_is_non_empty_and_contains_canonical_names() -> None:
    assert set(REPLAY_LINEAGE_REQUIRED_FIELDS) == {"registry_entry_id", "message_snapshot_id"}


def test_migration_mode_keeps_events_missing_lineage(tmp_path: Path) -> None:
    ap = tmp_path / "a.json"
    dp = tmp_path / "d.json"
    ap.write_text(_empty_ledger_payload("alerts"), encoding="utf-8")
    dp.write_text(_empty_ledger_payload("decisions"), encoding="utf-8")

    events, err = build_timeline_events(
        bundle=_bundle(with_lineage=False),
        decisions=[],
        alerts=[],
        require_lineage=False,
    )
    assert err is None
    assert len(events) >= 2
    for e in events:
        for k in REPLAY_LINEAGE_REQUIRED_FIELDS:
            assert k in e


def test_strict_mode_drops_events_missing_lineage() -> None:
    events, err = build_timeline_events(
        bundle=_bundle(with_lineage=False),
        decisions=[],
        alerts=[],
        require_lineage=True,
    )
    assert err is None
    for e in events:
        assert missing_required_lineage_fields(e) == []


def test_bundle_lineage_propagates_to_bundle_authoritative_event() -> None:
    events, err = build_timeline_events(
        bundle=_bundle(with_lineage=True),
        decisions=[],
        alerts=[],
        require_lineage=True,
    )
    assert err is None
    bundle_ev = next(e for e in events if e["event_id"] == "evt_bundle_authoritative")
    assert bundle_ev["registry_entry_id"] == "reg_short_v1"
    assert bundle_ev["message_snapshot_id"] == "msg_snap_001"


def test_audit_counts_lineage_completeness() -> None:
    events, _ = build_timeline_events(
        bundle=_bundle(with_lineage=True),
        decisions=[
            {
                "timestamp": "2026-03-01T00:00:00+00:00",
                "asset_id": "T1",
                "decision_type": "hold",
                "founder_note": "",
                "message_snapshot_id": "msg_snap_001",
                "linked_registry_entry_id": "reg_short_v1",
            }
        ],
        alerts=[],
    )
    audit = audit_timeline_events_for_lineage(events)
    assert audit["total"] == len(events)
    assert audit["with_full_required_lineage"] >= 3


def test_decision_event_inherits_bundle_lineage_when_missing() -> None:
    events, _ = build_timeline_events(
        bundle=_bundle(with_lineage=True),
        decisions=[
            {
                "timestamp": "2026-03-01T00:00:00+00:00",
                "asset_id": "T1",
                "decision_type": "hold",
                "founder_note": "",
            }
        ],
        alerts=[],
    )
    dec_ev = next(e for e in events if e["event_type"] == "decision_event")
    assert dec_ev["registry_entry_id"] == "reg_short_v1"
    assert dec_ev["message_snapshot_id"] == "msg_snap_001"
