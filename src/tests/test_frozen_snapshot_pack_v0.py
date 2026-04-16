"""Stage 5 stub — frozen snapshot pack manifest + demo API."""

from __future__ import annotations

import shutil
from pathlib import Path

from phase47_runtime.frozen_snapshot_pack_v0 import load_frozen_snapshot_pack_v0
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState


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


def test_load_frozen_pack_resolves_steps(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "frozen_snapshot_pack_v0.json"
    dst = tmp_path / "data" / "mvp" / "frozen_snapshot_pack_v0.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    out = load_frozen_snapshot_pack_v0(tmp_path, lang="ko")
    assert out["ok"] is True
    steps = out.get("investor_demo_steps_resolved") or []
    assert len(steps) >= 4
    assert all(s.get("label") for s in steps)


def test_dispatch_frozen_snapshot_pack(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "frozen_snapshot_pack_v0.json"
    dst = tmp_path / "data" / "mvp" / "frozen_snapshot_pack_v0.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    st = _runtime(tmp_path)
    code, obj = dispatch_json(st, method="GET", path="/api/demo/frozen-snapshot-pack", body=None, query={"lang": "en"})
    assert code == 200 and obj.get("ok") is True
    assert obj.get("pack", {}).get("pack_id")


def test_dispatch_frozen_pack_missing_returns_404(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, obj = dispatch_json(st, method="GET", path="/api/demo/frozen-snapshot-pack", body=None)
    assert code == 404 and obj.get("error") == "frozen_snapshot_pack_missing"
