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


def test_survey_has_all_ten_question_ids() -> None:
    out = build_mvp_spec_survey_v0(_repo())
    ids = {q["id"] for q in (out.get("questions") or [])}
    expected = {
        "Q1_today_registry_only",
        "Q2_active_family_per_horizon",
        "Q3_challenger_active_distinction",
        "Q4_artifact_required_for_active",
        "Q5_message_store_path",
        "Q6_message_headline_why_now_rationale",
        "Q7_same_ticker_different_horizon_position",
        "Q8_rank_movement_on_mock_price_tick",
        "Q9_information_and_research_layers_present",
        "Q10_replay_lineage_join_present",
    }
    assert expected.issubset(ids)


def test_survey_reports_all_automated_ok_flag() -> None:
    out = build_mvp_spec_survey_v0(_repo())
    assert isinstance(out.get("all_automated_ok"), bool)
    assert isinstance(out.get("manual_or_runtime_proof"), list)


def test_repo_bundle_survey_all_ten_automated_ok(monkeypatch) -> None:
    """Guard against regression: the canonical repo bundle + registry source must keep Q1-Q10 green."""
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    out = build_mvp_spec_survey_v0(_repo())
    bad = [q for q in out.get("questions") or [] if not q.get("ok")]
    assert not bad, f"Survey failed for: {[(q['id'], q.get('detail')) for q in bad]}"
    assert out.get("all_automated_ok") is True


def test_runtime_health_payload_includes_survey() -> None:
    from phase51_runtime.cockpit_health_surface import build_cockpit_runtime_health_payload

    payload = build_cockpit_runtime_health_payload(repo_root=_repo(), lang="en")
    survey = payload.get("mvp_product_spec_survey_v0") or {}
    qs = survey.get("questions") or []
    ids = {q.get("id") for q in qs}
    for qid in (
        "Q6_message_headline_why_now_rationale",
        "Q7_same_ticker_different_horizon_position",
        "Q8_rank_movement_on_mock_price_tick",
        "Q9_information_and_research_layers_present",
        "Q10_replay_lineage_join_present",
    ):
        assert qid in ids, f"runtime health must surface {qid}"
