"""METIS MVP Build Plan §6 / Stage 3 — Research surface contract acceptance (no browser).

Maps to Unified Build Plan Stage 3 acceptance bullets:
- Detail carries message → information → research (structured keys).
- Ask AI (governed conversation) responds to why_now / what_changed / what_to_watch.
- Bounded sandbox returns horizon_scan with multiple horizons when the asset exists on the board.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase47_runtime.governed_conversation import process_governed_prompt
from phase47_runtime.message_layer_v1 import MESSAGE_LAYER_V1_KEYS
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.sandbox_v1 import run_sandbox_v1
from phase47_runtime.today_spectrum import build_today_object_detail_payload

CONTRACT_STAGE3 = "METIS_STAGE3_RESEARCH_SURFACE_ACCEPTANCE_V0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _phase46_bundle_path() -> Path:
    p = _repo_root() / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    if not p.is_file():
        pytest.skip("phase46 bundle missing")
    return p


def test_stage3_today_object_detail_message_information_research() -> None:
    repo = _repo_root()
    out = build_today_object_detail_payload(
        repo_root=repo,
        asset_id="DEMO_KR_A",
        horizon="short",
        lang="en",
        mock_price_tick="0",
    )
    assert out.get("ok") is True, out
    assert out.get("detail_contract") == "SPRINT4_MESSAGE_INFORMATION_RESEARCH_V0"
    msg = out.get("message") or {}
    assert isinstance(msg, dict)
    for k in ("headline", "why_now", "what_changed", "what_to_watch", "linked_registry_entry_id", "linked_artifact_id"):
        assert k in msg, f"missing message.{k}"
        assert str(msg.get(k) or "").strip(), f"empty message.{k}"
    for k in MESSAGE_LAYER_V1_KEYS:
        assert k in msg
    info = out.get("information") or {}
    assert isinstance(info, dict)
    assert info.get("supporting_signals") or info.get("evidence_summary")
    res = out.get("research") or {}
    assert isinstance(res, dict)
    assert res.get("horizon_lens_compare") or res.get("summary") or res.get("deeper_rationale")
    hlc = res.get("horizon_lens_compare")
    if isinstance(hlc, list):
        assert len(hlc) >= 1, "expected at least one alternate-horizon lens row"
        assert all("horizon" in x for x in hlc if isinstance(x, dict))


def test_stage3_get_today_object_api() -> None:
    repo = _repo_root()
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_phase46_bundle_path())
    code, obj = dispatch_json(
        st,
        method="GET",
        path="/api/today/object?asset_id=DEMO_KR_A&horizon=short&lang=en",
        body=None,
    )
    assert code == 200
    assert obj.get("ok") is True
    assert (obj.get("message") or {}).get("headline")


def test_stage3_ask_ai_governed_chips_use_copilot_context() -> None:
    bpath = _phase46_bundle_path()
    bundle = json.loads(bpath.read_text(encoding="utf-8"))
    ctx = {
        "source": "today_detail",
        "asset_id": "DEMO_KR_A",
        "why_now": "Seed: catalyst calendar thin.",
        "what_to_watch": "Seed: next print margin path.",
    }
    for prompt, expect_substr in (
        ("why now", "**Why now**"),
        ("what changed", "**What changed**"),
        ("what to watch", "**What to watch**"),
    ):
        r = process_governed_prompt(bundle, prompt, copilot_context=ctx)
        assert r.get("governed") is True
        assert expect_substr in (r.get("body_markdown") or "")


def test_stage3_sandbox_horizon_scan_multi_horizon() -> None:
    repo = _repo_root()
    st = CockpitRuntimeState.from_paths(repo_root=repo, phase46_bundle_path=_phase46_bundle_path())
    out = run_sandbox_v1(
        bundle=st.bundle,
        repo_root=repo,
        body={"hypothesis": "Stage3 acceptance: cross-horizon scan", "asset_id": "DEMO_KR_A", "horizon": "short"},
        lang="en",
    )
    assert out.get("ok") is True
    scan = (out.get("result") or {}).get("horizon_scan") or []
    assert isinstance(scan, list)
    horizons = {str(x.get("horizon")) for x in scan if isinstance(x, dict)}
    assert len(horizons) >= 2, f"expected ≥2 horizons in scan, got {horizons!r} contract={CONTRACT_STAGE3}"
