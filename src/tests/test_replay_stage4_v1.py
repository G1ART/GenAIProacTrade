"""Stage 4 — message snapshot store, counterfactual templates + preview APIs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from metis_brain.message_snapshots_store import get_message_snapshot
from phase47_runtime.replay_counterfactual_v1 import CF_TEMPLATES_V1, counterfactual_preview_v1, counterfactual_templates_v1_payload
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.today_spectrum import build_today_object_detail_payload


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime(tmp_path: Path) -> CockpitRuntimeState:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    import json

    bundle = {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {"asset_id": "x"},
        "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
        "alert_ledger_path": str(ap),
        "decision_trace_ledger_path": str(dp),
    }
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


def test_counterfactual_templates_has_four() -> None:
    p = counterfactual_templates_v1_payload("ko")
    assert p["ok"] is True
    assert len(p.get("templates") or []) == 4


def test_counterfactual_preview_known_template(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    out = counterfactual_preview_v1(
        repo_root=tmp_path,
        template_id=CF_TEMPLATES_V1[0]["template_id"],
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="ko",
        mock_price_tick="0",
    )
    assert out["ok"] is True
    assert out.get("baseline", {}).get("message_snapshot_id")
    assert "stressed" in out


def test_today_object_detail_writes_snapshot(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    det = build_today_object_detail_payload(
        repo_root=tmp_path,
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="ko",
        mock_price_tick="0",
    )
    assert det.get("ok") is True
    sid = (det.get("replay_lineage_join_v1") or {}).get("message_snapshot_id")
    assert sid
    snap = get_message_snapshot(tmp_path, str(sid))
    assert snap and snap.get("asset_id") == "DEMO_KR_A"
    rs = snap.get("registry_surface_v1") or {}
    assert rs.get("contract") == "TODAY_REGISTRY_SURFACE_V1"


def test_dispatch_message_snapshot_and_cf_apis(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code0, ob = dispatch_json(
        st,
        method="GET",
        path="/api/today/object",
        body=None,
        query={"asset_id": "DEMO_KR_A", "horizon": "short", "lang": "ko"},
    )
    assert code0 == 200 and ob.get("ok") is True
    sid = (ob.get("replay_lineage_join_v1") or {}).get("message_snapshot_id")
    code, snap = dispatch_json(
        st,
        method="GET",
        path="/api/replay/message-snapshot",
        body=None,
        query={"snapshot_id": sid},
    )
    assert code == 200 and snap.get("ok") is True
    assert isinstance(snap.get("registry_surface_v1"), dict)
    assert (snap.get("registry_surface_v1") or {}).get("contract") == "TODAY_REGISTRY_SURFACE_V1"
    code_alias, snap_alias = dispatch_json(
        st,
        method="GET",
        path="/api/today/message-snapshot",
        body=None,
        query={"snapshot_id": sid},
    )
    assert code_alias == 200 and snap_alias == snap
    code2, tj = dispatch_json(st, method="GET", path="/api/replay/counterfactual-templates", body=None, query={"lang": "ko"})
    assert code2 == 200 and len(tj.get("templates") or []) == 4
    tid = tj["templates"][0]["template_id"]
    code3, pj = dispatch_json(
        st,
        method="GET",
        path="/api/replay/counterfactual-preview",
        body=None,
        query={"template_id": tid, "asset_id": "DEMO_KR_A", "horizon": "short", "lang": "ko"},
    )
    assert code3 == 200 and pj.get("ok") is True


def test_dispatch_decision_append_persists_replay_lineage_fields(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    body = {
        "decision_type": "hold",
        "asset_id": "DEMO_KR_A",
        "founder_note": "n",
        "linked_message_summary": "headline snap",
        "linked_authoritative_artifact": "phase46_bundle",
        "linked_research_provenance": "today_object_detail_v1",
        "replay_lineage_pointer": "seed:replay_lineage_v0",
        "message_snapshot_id": "msg_snap:v1:ledger_test_1",
        "linked_registry_entry_id": "reg_demo",
        "linked_artifact_id": "art_demo",
    }
    code, out = dispatch_json(
        st,
        method="POST",
        path="/api/decisions",
        body=json.dumps(body).encode("utf-8"),
    )
    assert code == 200 and out.get("ok") is True
    row = out.get("decision") or {}
    assert row.get("message_snapshot_id") == "msg_snap:v1:ledger_test_1"
    assert row.get("replay_lineage_pointer") == "seed:replay_lineage_v0"
    assert row.get("linked_registry_entry_id") == "reg_demo"


def test_message_snapshot_missing_returns_404(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, obj = dispatch_json(
        st,
        method="GET",
        path="/api/replay/message-snapshot",
        body=None,
        query={"snapshot_id": "msg_snap:v1:doesnotexist000000"},
    )
    assert code == 404 and obj.get("error") == "snapshot_not_found"
    code2, obj2 = dispatch_json(
        st,
        method="GET",
        path="/api/today/message-snapshot",
        body=None,
        query={"snapshot_id": "msg_snap:v1:doesnotexist000000"},
    )
    assert code2 == 404 and obj2.get("error") == "snapshot_not_found"


def test_replay_timeline_today_lineage_join_injects_matching_events(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    st.alert_ledger_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "alerts": [
                    {
                        "alert_id": "a_demo",
                        "alert_timestamp": "2026-01-02T00:00:00+00:00",
                        "asset_id": "DEMO_KR_A",
                        "alert_class": "signal",
                        "message_summary": "seed alert",
                        "triggering_source_artifact": "artifact_x",
                        "requires_attention": True,
                        "status": "open",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    code, tl = dispatch_json(
        st,
        method="GET",
        path="/api/replay/timeline",
        body=None,
        query={"asset_id": "DEMO_KR_A", "horizon": "short", "lang": "ko"},
    )
    assert code == 200 and tl.get("ok") is True
    ntf = tl.get("now_then_frame_v1")
    assert ntf and ntf.get("contract") == "REPLAY_NOW_THEN_FRAME_V1"
    assert ntf.get("body_then") and ntf.get("body_now")
    join = tl.get("today_lineage_join_v1")
    assert join and join.get("contract") == "REPLAY_LINEAGE_JOIN_V1"
    assert join.get("message_snapshot_id")
    ev_alert = next((e for e in tl.get("events") or [] if str(e.get("event_id") or "").startswith("evt_alert")), None)
    assert ev_alert and str(ev_alert.get("message_snapshot_id") or "")
    eid = str(ev_alert.get("event_id") or "")
    code2, mbj = dispatch_json(
        st,
        method="GET",
        path="/api/replay/micro-brief",
        body=None,
        query={"event_id": eid, "asset_id": "DEMO_KR_A", "horizon": "short", "lang": "ko"},
    )
    assert code2 == 200
    m = mbj.get("micro_brief") or {}
    assert m.get("message_snapshot_id") == join.get("message_snapshot_id")
    rs_tl = tl.get("registry_surface_v1") or {}
    assert rs_tl.get("contract") == "TODAY_REGISTRY_SURFACE_V1"
    rs_mb = m.get("registry_surface_v1") or {}
    assert rs_mb.get("contract") == "TODAY_REGISTRY_SURFACE_V1"
