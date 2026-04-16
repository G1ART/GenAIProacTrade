"""Slice B — message_snapshot_id threads Today detail → Ask → sandbox."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from metis_brain.message_snapshot_copilot_bridge_v0 import (
    enrich_copilot_context_from_message_snapshot,
    snapshot_record_to_copilot_context,
)
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.sandbox_v1 import run_sandbox_v1
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


def test_snapshot_record_to_copilot_roundtrip_keys() -> None:
    rec = {
        "asset_id": "DEMO_KR_A",
        "horizon": "short",
        "active_model_family": "fam",
        "message": {"headline": "H", "why_now": "W"},
        "spectrum": {"spectrum_band": "left"},
        "replay_lineage_join_v1": {"message_snapshot_id": "snap:x", "replay_lineage_pointer": "rp"},
    }
    ctx = snapshot_record_to_copilot_context(rec)
    assert ctx.get("headline") == "H"
    assert ctx.get("why_now") == "W"
    assert ctx.get("message_snapshot_id") == "snap:x"


def test_today_object_detail_top_level_message_snapshot_id(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    det = build_today_object_detail_payload(
        repo_root=tmp_path,
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="en",
        mock_price_tick="0",
    )
    assert det.get("ok") is True
    sid = det.get("message_snapshot_id")
    rj = det.get("replay_lineage_join_v1") or {}
    assert sid and sid == rj.get("message_snapshot_id")
    assert (det.get("research") or {}).get("message_snapshot_id") == sid


def test_conversation_resolves_message_snapshot_for_why_now(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code0, ob = dispatch_json(
        st,
        method="GET",
        path="/api/today/object?asset_id=DEMO_KR_A&horizon=short&lang=en",
        body=None,
    )
    assert code0 == 200 and ob.get("ok") is True
    sid = ob.get("message_snapshot_id")
    assert sid
    body = {"text": "why now", "message_snapshot_id": sid}
    code, r = dispatch_json(
        st,
        method="POST",
        path="/api/conversation",
        body=json.dumps(body).encode(),
    )
    assert code == 200
    assert r.get("ok") is True
    assert r.get("message_snapshot_id") == sid
    assert "**Why now**" in (r.get("response") or {}).get("body_markdown", "")


def test_conversation_unknown_snapshot_returns_error(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    body = {"text": "why now", "message_snapshot_id": "msg_snap:v1:does_not_exist_xyz"}
    code, r = dispatch_json(
        st,
        method="POST",
        path="/api/conversation",
        body=json.dumps(body).encode(),
    )
    assert code == 422
    assert r.get("ok") is False
    assert r.get("error") == "snapshot_not_found"


def test_sandbox_accepts_message_snapshot_prefills_asset(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    det = build_today_object_detail_payload(
        repo_root=tmp_path,
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="en",
        mock_price_tick="0",
    )
    sid = det.get("message_snapshot_id")
    assert sid
    out = run_sandbox_v1(
        bundle=st.bundle,
        repo_root=tmp_path,
        body={"hypothesis": "Slice B link check", "message_snapshot_id": sid},
        lang="en",
    )
    assert out.get("ok") is True
    echo = out.get("inputs_echo") or {}
    assert echo.get("message_snapshot_id") == sid
    assert echo.get("asset_id") == "DEMO_KR_A"
    bullets = (out.get("result") or {}).get("summary_bullets") or []
    assert any("message_snapshot" in str(b).lower() for b in bullets)


def test_enrich_respects_nonempty_base(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    det = build_today_object_detail_payload(
        repo_root=tmp_path,
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="en",
        mock_price_tick="0",
    )
    sid = str(det.get("message_snapshot_id") or "")
    merged, err = enrich_copilot_context_from_message_snapshot(
        tmp_path, sid, {"headline": "OverrideHeadline"}
    )
    assert err is None
    assert merged.get("headline") == "OverrideHeadline"
