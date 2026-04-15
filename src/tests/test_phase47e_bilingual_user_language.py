"""Phase 47e: KO/EN locale API + dispatch wiring."""

from __future__ import annotations

import json
from pathlib import Path

from phase47_runtime.home_feed import build_home_feed_payload
from phase47_runtime.phase47e_user_locale import export_shell_locale_dict, normalize_lang, t
from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState


def _minimal_bundle() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {
            "asset_id": "research_engine_fixture_cohort_x",
            "headline_message": "Closed under narrow claims.",
            "current_stance": "hold_closeout_until_named_new_source_or_new_evidence_v1",
            "closeout_status": "closed_pending_new_evidence",
            "reopen_requires_named_source": True,
            "what_changed": ["Diagnostic label refined."],
            "trace_links": {"p44": "/tmp/x.json"},
        },
        "cockpit_state": {
            "cohort_aggregate": {
                "founder_primary_status": "watching_for_new_evidence",
                "decision_card": {"title": "Stance", "body": "Hold until new evidence."},
            }
        },
        "representative_pitch": {"top_level_pitch": "pitch"},
        "drilldown_examples": {},
    }


def _runtime(tmp_path: Path) -> CockpitRuntimeState:
    ap = tmp_path / "a.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp = tmp_path / "d.json"
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    bpath = tmp_path / "b.json"
    bundle = _minimal_bundle()
    bundle["alert_ledger_path"] = str(ap)
    bundle["decision_trace_ledger_path"] = str(dp)
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


def test_normalize_lang_defaults_ko() -> None:
    assert normalize_lang(None) == "ko"
    assert normalize_lang("") == "ko"
    assert normalize_lang("EN") == "en"


def test_export_shell_locale_has_nav_keys() -> None:
    m = export_shell_locale_dict("ko")
    assert m.get("nav.home")
    assert m.get("nav.ask_ai")


def test_home_feed_lang_differs(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    ko = build_home_feed_payload(st, lang="ko")
    en = build_home_feed_payload(st, lang="en")
    assert ko.get("lang") == "ko" and en.get("lang") == "en"
    assert ko["today"]["title"] != en["today"]["title"]


def test_dispatch_locale_and_overview_lang(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, loc = dispatch_json(st, method="GET", path="/api/locale", body=None, query={"lang": "en"})
    assert code == 200 and loc.get("ok") is True
    assert loc.get("lang") == "en"
    assert loc.get("strings", {}).get("nav.home") == "Home"

    code2, ov = dispatch_json(
        st,
        method="GET",
        path="/api/overview",
        body=None,
        query={"lang": "en"},
        headers=None,
    )
    assert code2 == 200 and ov.get("lang") == "en"
    nav = ov["user_first"]["navigation"]["primary_navigation"]
    assert nav[0]["label"] == "Home"


def test_dispatch_respects_x_user_language_header(tmp_path: Path) -> None:
    st = _runtime(tmp_path)
    code, ov = dispatch_json(
        st,
        method="GET",
        path="/api/overview",
        body=None,
        query={},
        headers={"X-User-Language": "en"},
    )
    assert code == 200
    assert ov.get("lang") == "en"


def test_t_nav_home_ko() -> None:
    assert t("ko", "nav.home") == "홈"
