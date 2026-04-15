"""Sprint 1 stub — Today spectrum API."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from phase47_runtime.home_feed import build_home_feed_payload
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.today_spectrum import build_today_spectrum_payload


def _copy_seed(tmp: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    src = repo / "data" / "mvp" / "today_spectrum_seed_v1.json"
    if not src.is_file():
        pytest.skip("today_spectrum_seed_v1.json missing")
    dst = tmp / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _runtime(tmp_path: Path) -> CockpitRuntimeState:
    _copy_seed(tmp_path)
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
    }
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


def test_build_today_spectrum_includes_message_layer(tmp_path: Path) -> None:
    _copy_seed(tmp_path)
    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out["ok"] is True
    assert out.get("message_layer_version") == 1
    row_a = next(x for x in out["rows"] if x.get("asset_id") == "DEMO_KR_A")
    assert row_a.get("spectrum_band") in ("left", "center", "right")
    msg = row_a.get("message") or {}
    assert msg.get("message_id")
    assert "밸류" in (msg.get("headline") or "") or "방어" in (msg.get("headline") or "")


def test_build_today_spectrum_short_vs_long_differs(tmp_path: Path) -> None:
    _copy_seed(tmp_path)
    ko_short = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    ko_long = build_today_spectrum_payload(repo_root=tmp_path, horizon="long", lang="ko")
    assert ko_short["ok"] and ko_long["ok"]
    assert ko_short["active_model_family"] != ko_long["active_model_family"]
    ids_s = {r["asset_id"] for r in ko_short["rows"]}
    ids_l = {r["asset_id"] for r in ko_long["rows"]}
    assert ids_s & ids_l


def test_dispatch_today_spectrum_ko(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, obj = dispatch_json(st, method="GET", path="/api/today/spectrum", body=None, query={"lang": "ko", "horizon": "short"})
    assert code == 200 and obj.get("ok") is True
    assert obj.get("horizon") == "short"
    assert obj.get("horizon_label")
    assert len(obj.get("rows") or []) >= 1


def test_mock_price_tick_changes_short_leader(tmp_path: Path) -> None:
    _copy_seed(tmp_path)
    b0 = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko", mock_price_tick="0")
    b1 = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko", mock_price_tick="1")
    assert b0["rows"][0]["asset_id"] != b1["rows"][0]["asset_id"]
    assert b1.get("mock_price_tick") == "1"


def test_home_feed_has_today_spectrum_summary(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    payload = build_home_feed_payload(st, lang="ko")
    assert payload.get("ok") is True
    summ = payload.get("today_spectrum_summary")
    assert summ and summ.get("top_messages")
    assert len(summ["top_messages"]) <= 2


def test_dispatch_invalid_horizon_404(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, obj = dispatch_json(st, method="GET", path="/api/today/spectrum", body=None, query={"horizon": "nope"})
    assert code == 404
    assert obj.get("error") == "invalid_horizon"
