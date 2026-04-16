"""Replay aging brief — journal + sandbox + horizon strip."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from phase47_runtime.replay_aging_brief import build_replay_aging_brief
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.routes import dispatch_json


def test_replay_aging_brief_dispatch(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p46 = repo / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    if not p46.is_file():
        pytest.skip("phase46 bundle missing")
    (tmp_path / "data" / "mvp").mkdir(parents=True)
    shutil.copy(repo / "data/mvp/today_spectrum_seed_v1.json", tmp_path / "data/mvp/today_spectrum_seed_v1.json")
    bpath = tmp_path / "p46.json"
    bpath.write_text(p46.read_text(encoding="utf-8"), encoding="utf-8")
    dp = tmp_path / "dec.json"
    dp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decisions": [
                    {
                        "timestamp": "2026-01-02T00:00:00+00:00",
                        "asset_id": "DEMO_KR_A",
                        "decision_type": "watch",
                        "founder_note": "note one",
                        "linked_message_summary": "m",
                        "linked_authoritative_artifact": "a",
                        "linked_research_provenance": "r",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sp = tmp_path / "sandbox_runs_ledger_v1.json"
    sp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "runs": [
                    {
                        "saved_at": "2026-01-03T00:00:00+00:00",
                        "run_id": "runxyz",
                        "inputs_echo": {"hypothesis": "h1", "asset_id": "DEMO_KR_A"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath, decision_ledger_path=dp)
    st.decision_ledger_path = dp
    st.sandbox_ledger_path = sp

    code, obj = dispatch_json(
        st,
        method="GET",
        path="/api/replay/aging-brief?asset_id=DEMO_KR_A&lang=en",
        body=None,
    )
    assert code == 200
    assert obj.get("ok") is True
    assert obj.get("asset_id") == "DEMO_KR_A"
    assert len(obj.get("decisions_tail") or []) == 1
    assert len(obj.get("sandbox_runs_tail") or []) == 1
    assert len(obj.get("horizon_spectrum_strip") or []) >= 1

    code2, bad = dispatch_json(st, method="GET", path="/api/replay/aging-brief", body=None)
    assert code2 == 400


def test_build_replay_aging_brief_empty_asset(tmp_path: Path) -> None:
    dp = tmp_path / "d.json"
    dp.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps({"schema_version": 1, "runs": []}), encoding="utf-8")
    out = build_replay_aging_brief(
        repo_root=tmp_path,
        decision_ledger_path=dp,
        sandbox_ledger_path=sp,
        asset_id="",
        lang="en",
    )
    assert out.get("ok") is False
