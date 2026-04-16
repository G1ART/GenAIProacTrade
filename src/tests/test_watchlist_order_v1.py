"""Watchlist display order — MVP Build Plan Stage 1."""

from __future__ import annotations

import json
from pathlib import Path

from phase47_runtime.home_feed import bundle_watch_candidate_asset_ids, build_home_feed_payload
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState
from phase47_runtime.watchlist_order_v1 import (
    merge_watchlist_display_order,
    validate_full_reorder_payload,
    watchlist_order_path,
)


def test_merge_watchlist_display_order() -> None:
    canon = ["A", "B", "C"]
    assert merge_watchlist_display_order(canon, []) == canon
    assert merge_watchlist_display_order(canon, ["C", "A", "B"]) == ["C", "A", "B"]
    assert merge_watchlist_display_order(["A", "B", "C"], ["C", "X"]) == ["C", "A", "B"]


def test_validate_full_reorder_payload() -> None:
    ok, err = validate_full_reorder_payload(["a"], allowed_ordered=["a", "b"])
    assert err == "ordered_asset_ids_length_mismatch"
    ok2, err2 = validate_full_reorder_payload(["a", "b"], allowed_ordered=["a", "b"])
    assert err2 is None and ok2 == ["a", "b"]
    _ok3, err3 = validate_full_reorder_payload(["a", "a"], allowed_ordered=["a", "b"])
    assert err3 and "duplicate" in err3


def _bundle_with_cohort() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {
            "asset_id": "PRIMARY_X",
            "headline_message": "h",
            "cohort_symbols": ["SYM_B", "SYM_C"],
        },
        "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
        "representative_pitch": {},
        "drilldown_examples": {},
    }


def _runtime(tmp_path: Path, bundle: dict) -> CockpitRuntimeState:
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    bundle = {**bundle, "alert_ledger_path": str(ap), "decision_trace_ledger_path": str(dp)}
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    (tmp_path / "data" / "mvp").mkdir(parents=True, exist_ok=True)
    seed = Path(__file__).resolve().parents[2] / "data" / "mvp" / "today_spectrum_seed_v1.json"
    if seed.is_file():
        import shutil

        shutil.copyfile(seed, tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json")
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


def test_home_feed_respects_saved_watchlist_order(tmp_path: Path) -> None:
    st = _runtime(tmp_path, _bundle_with_cohort())
    canon = bundle_watch_candidate_asset_ids(st.bundle)
    assert canon == ["PRIMARY_X", "SYM_B", "SYM_C"]
    p = watchlist_order_path(tmp_path)
    p.write_text(
        json.dumps({"schema_version": 1, "ordered_asset_ids": ["SYM_C", "PRIMARY_X", "SYM_B"]}),
        encoding="utf-8",
    )
    payload = build_home_feed_payload(st, lang="en")
    assert payload["ok"] is True
    tsui = payload.get("today_spectrum_ui") or {}
    assert tsui.get("watchlist_asset_ids") == ["SYM_C", "PRIMARY_X", "SYM_B"]
    wb = payload.get("watchlist_block") or {}
    assert wb.get("reorderable_asset_ids") == ["SYM_C", "PRIMARY_X", "SYM_B"]


def test_dispatch_watchlist_order_post_get(tmp_path: Path) -> None:
    st = _runtime(tmp_path, _bundle_with_cohort())
    code0, g0 = dispatch_json(st, method="GET", path="/api/today/watchlist-order", body=None)
    assert code0 == 200 and g0.get("effective_ordered_ids") == ["PRIMARY_X", "SYM_B", "SYM_C"]
    perm = ["SYM_B", "SYM_C", "PRIMARY_X"]
    code1, p1 = dispatch_json(
        st,
        method="POST",
        path="/api/today/watchlist-order",
        body=json.dumps({"ordered_asset_ids": perm}).encode("utf-8"),
    )
    assert code1 == 200 and p1.get("ok") is True
    payload = build_home_feed_payload(st, lang="en")
    assert (payload.get("today_spectrum_ui") or {}).get("watchlist_asset_ids") == perm
    code2, g2 = dispatch_json(st, method="GET", path="/api/today/watchlist-order", body=None)
    assert g2.get("stored_raw_order") == perm
