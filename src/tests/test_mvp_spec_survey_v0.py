"""MVP spec survey — brain bundle + env signals."""

from __future__ import annotations

from pathlib import Path

from metis_brain.mvp_spec_survey_v0 import build_mvp_spec_survey_v0


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def test_survey_with_repo_bundle_has_questions() -> None:
    out = build_mvp_spec_survey_v0(_repo())
    assert out.get("contract") == "METIS_MVP_SPEC_SURVEY_V0"
    qs = out.get("questions") or []
    assert len(qs) >= 5
    ids = {q["id"] for q in qs}
    assert "Q1_today_registry_only" in ids


def test_survey_seed_mode_q1_false(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("METIS_TODAY_SOURCE", "seed")
    out = build_mvp_spec_survey_v0(tmp_path)
    q1 = next(q for q in out["questions"] if q["id"] == "Q1_today_registry_only")
    assert q1.get("ok") is False
