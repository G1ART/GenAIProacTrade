"""Sandbox v1 — deterministic bundle + Today seed cross-check."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.routes import dispatch_json
from phase47_runtime.sandbox_runs_ledger import append_sandbox_run, get_sandbox_run, list_sandbox_runs, load_sandbox_runs_ledger
from phase47_runtime.sandbox_v1 import run_sandbox_v1


def _bundle_path() -> Path:
    repo = Path(__file__).resolve().parents[2]
    p = repo / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    if not p.is_file():
        pytest.skip("phase46 bundle missing")
    return p


def test_sandbox_hypothesis_required() -> None:
    repo = Path(__file__).resolve().parents[2]
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_bundle_path())
    out = run_sandbox_v1(bundle=st.bundle, repo_root=repo, body={}, lang="en")
    assert out["ok"] is False
    assert out.get("error") == "hypothesis_required"


def test_sandbox_invalid_horizon() -> None:
    repo = Path(__file__).resolve().parents[2]
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_bundle_path())
    out = run_sandbox_v1(
        bundle=st.bundle,
        repo_root=repo,
        body={"hypothesis": "test", "horizon": "nope"},
        lang="en",
    )
    assert out["ok"] is False
    assert out.get("error") == "invalid_horizon"


def test_sandbox_with_asset_horizon_scan() -> None:
    repo = Path(__file__).resolve().parents[2]
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_bundle_path())
    out = run_sandbox_v1(
        bundle=st.bundle,
        repo_root=repo,
        body={"hypothesis": "What would move the band?", "asset_id": "DEMO_KR_A", "horizon": "short"},
        lang="ko",
    )
    assert out["ok"] is True
    assert out.get("contract") == "SANDBOX_V1"
    assert out.get("run_id") and len(out["run_id"]) == 16
    res = out.get("result") or {}
    assert res.get("summary_bullets")
    scan = res.get("horizon_scan")
    assert isinstance(scan, list) and len(scan) >= 1


def test_sandbox_pit_stub_note() -> None:
    repo = Path(__file__).resolve().parents[2]
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_bundle_path())
    out = run_sandbox_v1(
        bundle=st.bundle,
        repo_root=repo,
        body={"hypothesis": "PIT check", "pit_mode": "pit_stub"},
        lang="en",
    )
    assert out["ok"] is True
    note = (out.get("result") or {}).get("pit_note")
    assert note and "stub" in note.lower()


def test_sandbox_dispatch_post() -> None:
    repo = Path(__file__).resolve().parents[2]
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_bundle_path())
    code, obj = dispatch_json(
        st,
        method="POST",
        path="/api/sandbox/run?lang=en",
        body=json.dumps({"hypothesis": "Cross-check stance", "asset_id": "DEMO_KR_A", "save": False}).encode(),
    )
    assert code == 200
    assert obj.get("ok") is True
    assert obj.get("run_id")
    assert obj.get("persisted") is None


def test_sandbox_persist_and_list_api(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p46 = _bundle_path()
    (tmp_path / "data" / "mvp").mkdir(parents=True)
    shutil.copy(repo / "data/mvp/today_spectrum_seed_v1.json", tmp_path / "data/mvp/today_spectrum_seed_v1.json")
    bpath = tmp_path / "p46.json"
    bpath.write_text(p46.read_text(encoding="utf-8"), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    code, obj = dispatch_json(
        st,
        method="POST",
        path="/api/sandbox/run?lang=en",
        body=json.dumps({"hypothesis": "Ledger row", "asset_id": "DEMO_KR_A", "save": True}).encode(),
    )
    assert code == 200
    assert obj.get("persisted") is True
    assert st.sandbox_ledger_path.is_file()
    data = load_sandbox_runs_ledger(st.sandbox_ledger_path)
    assert len(data.get("runs") or []) >= 1
    code2, lst = dispatch_json(st, method="GET", path="/api/sandbox/runs?limit=5&lang=en", body=None)
    assert code2 == 200
    assert lst.get("ok") is True
    assert len(lst.get("runs") or []) >= 1


def test_sandbox_ledger_append_unit(tmp_path: Path) -> None:
    p = tmp_path / "sandbox_runs_ledger_v1.json"
    out = {
        "ok": True,
        "run_id": "abc",
        "contract": "SANDBOX_V1",
        "lang": "en",
        "inputs_echo": {"hypothesis": "h"},
        "result": {"summary_bullets": ["a"], "horizon_scan": [{"horizon": "short"}], "pit_note": None},
    }
    append_sandbox_run(p, out)
    runs = list_sandbox_runs(p, limit=10)
    assert len(runs) == 1
    assert runs[0]["run_id"] == "abc"
    got = get_sandbox_run(p, "abc")
    assert got and got["run_id"] == "abc"


def test_sandbox_get_dispatch(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p46 = _bundle_path()
    (tmp_path / "data" / "mvp").mkdir(parents=True)
    shutil.copy(repo / "data/mvp/today_spectrum_seed_v1.json", tmp_path / "data/mvp/today_spectrum_seed_v1.json")
    bpath = tmp_path / "p46.json"
    bpath.write_text(p46.read_text(encoding="utf-8"), encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    code, obj = dispatch_json(
        st,
        method="POST",
        path="/api/sandbox/run?lang=en",
        body=json.dumps({"hypothesis": "For GET", "asset_id": "DEMO_KR_A", "save": True}).encode(),
    )
    assert code == 200
    rid = obj["run_id"]
    code2, one = dispatch_json(st, method="GET", path="/api/sandbox/run?run_id=" + rid, body=None)
    assert code2 == 200
    assert one.get("run", {}).get("run_id") == rid
    code3, bad = dispatch_json(st, method="GET", path="/api/sandbox/run?run_id=nope_nope_nope", body=None)
    assert code3 == 404
    code4, miss = dispatch_json(st, method="GET", path="/api/sandbox/run", body=None)
    assert code4 == 400
