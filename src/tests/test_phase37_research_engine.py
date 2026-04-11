"""Phase 37 — research engine scaffolding."""

from __future__ import annotations

from pathlib import Path

from phase37.constitution import RESEARCH_ENGINE_ARTIFACTS, constitution_bundle_payload
from phase37.explanation_surface import render_explanation_prototype_md
from phase37.hypothesis_registry import HypothesisStatus, HypothesisV1, seed_hypothesis_join_key_mismatch_pit
from phase37.orchestrator import run_phase37_research_engine_backlog_sprint
from phase37.phase38_recommend import recommend_phase38_after_phase37
from phase37.pit_experiment import run_pit_experiment_scaffold
from phase37.review import write_phase37_research_engine_backlog_sprint_review_md


def test_constitution_has_six_pillars() -> None:
    assert len(RESEARCH_ENGINE_ARTIFACTS) == 6
    p = {x["pillar_id"] for x in RESEARCH_ENGINE_ARTIFACTS}
    assert "hypothesis_forge" in p
    assert "user_facing_explanation_layer" in p
    c = constitution_bundle_payload()
    assert c["version"] == 1


def test_hypothesis_v1_required_fields() -> None:
    h = seed_hypothesis_join_key_mismatch_pit()
    d = h.to_json_dict()
    assert d["hypothesis_id"]
    assert d["status"] == HypothesisStatus.UNDER_TEST.value
    assert d["falsifiers"]
    assert d["required_substrate_scope"]["fixture_symbols"]


def test_pit_scaffold_produces_record() -> None:
    from phase37.pit_experiment import default_pit_spec_for_join_mismatch_fixture

    h = seed_hypothesis_join_key_mismatch_pit()
    spec = default_pit_spec_for_join_mismatch_fixture()
    rec = run_pit_experiment_scaffold(hypothesis_id=h.hypothesis_id, spec=spec)
    assert rec.status == "recorded_scaffold"
    assert len(rec.inputs_snapshot.get("fixture_symbols") or []) == 8


def test_explanation_prototype_contains_sections() -> None:
    h = HypothesisV1(
        hypothesis_id="h1",
        title="t",
        economic_thesis="thesis",
        expected_mechanism="mech",
        applicable_horizon="1y",
        falsifiers=["f1"],
        status="draft",
    ).to_json_dict()
    md = render_explanation_prototype_md(
        hypothesis=h,
        signal_case={"symbol": "X", "residual_join_bucket": "b", "blocked_reason": "br"},
    )
    assert "What changed" in md
    assert "black-box" in md.lower()


def test_phase38_recommendation() -> None:
    r = recommend_phase38_after_phase37()
    assert "phase38_recommendation" in r
    assert "bind_pit" in r["phase38_recommendation"]


def test_orchestrator_writes_explanation(tmp_path: Path) -> None:
    expl = tmp_path / "expl.md"
    out = run_phase37_research_engine_backlog_sprint(
        phase36_1_bundle_path="",
        research_data_dir=str(tmp_path / "rd"),
        explanation_out_path=str(expl),
    )
    assert out["ok"] is True
    assert expl.is_file()
    assert "hyp_pit_join_key_mismatch" in expl.read_text(encoding="utf-8")


def test_write_review_md(tmp_path: Path) -> None:
    bundle = run_phase37_research_engine_backlog_sprint(
        phase36_1_bundle_path="",
        research_data_dir=str(tmp_path / "rd2"),
        explanation_out_path=str(tmp_path / "e.md"),
    )
    md = tmp_path / "r.md"
    write_phase37_research_engine_backlog_sprint_review_md(str(md), bundle=bundle)
    t = md.read_text(encoding="utf-8")
    assert "Phase 37" in t
    assert "Phase 38" in t
