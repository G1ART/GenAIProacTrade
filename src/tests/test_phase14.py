"""Phase 14 research engine kernel tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from research_engine.dossier import build_dossier
from research_engine.referee import decide_referee
from research_engine.reviewers import review_mechanism, review_pit_data
from research_engine.service import run_review_round


def test_mechanism_reject_short_rationale() -> None:
    r = review_mechanism(economic_rationale="x" * 40, mechanism_json={"primary_mechanism": "m" * 25})
    assert r.decision == "reject"


def test_mechanism_reject_no_primary_mechanism() -> None:
    r = review_mechanism(
        economic_rationale="y" * 120,
        mechanism_json={},
    )
    assert r.decision == "reject"


def test_pit_reject_failed_quality() -> None:
    r = review_pit_data(quality_context={"quality_class": "failed", "metrics_json": {}})
    assert r.decision == "reject"


def test_referee_thin_input_forces_sandbox_despite_pass_reviews() -> None:
    reviews = [
        {
            "reviewer_lens": "mechanism",
            "round_number": 1,
            "decision": "pass",
        },
        {
            "reviewer_lens": "pit_data",
            "round_number": 1,
            "decision": "pass",
        },
        {
            "reviewer_lens": "residual",
            "round_number": 1,
            "decision": "pass",
        },
        {
            "reviewer_lens": "compression",
            "round_number": 1,
            "decision": "pass",
        },
    ]
    out = decide_referee(
        reviews=reviews,
        quality_context={
            "quality_class": "thin_input",
            "metrics_json": {"insufficient_data_fraction": 1.0},
        },
    )
    assert out["final_decision"] == "sandbox"
    assert "thin_input" in out["rationale"].lower()


def test_referee_strong_all_pass_candidate_recipe() -> None:
    reviews = [
        {"reviewer_lens": "mechanism", "round_number": 1, "decision": "pass"},
        {"reviewer_lens": "pit_data", "round_number": 1, "decision": "pass"},
        {"reviewer_lens": "residual", "round_number": 1, "decision": "pass"},
        {"reviewer_lens": "compression", "round_number": 1, "decision": "pass"},
    ]
    out = decide_referee(
        reviews=reviews,
        quality_context={
            "quality_class": "strong",
            "metrics_json": {"insufficient_data_fraction": 0.1},
        },
    )
    assert out["final_decision"] == "candidate_recipe"
    assert out["final_decision"] in ("kill", "sandbox", "candidate_recipe")


def test_referee_mechanism_reject_kills() -> None:
    reviews = [
        {"reviewer_lens": "mechanism", "round_number": 1, "decision": "reject"},
        {"reviewer_lens": "pit_data", "round_number": 1, "decision": "pass"},
        {"reviewer_lens": "residual", "round_number": 1, "decision": "pass"},
    ]
    out = decide_referee(
        reviews=reviews,
        quality_context={"quality_class": "strong", "metrics_json": {}},
    )
    assert out["final_decision"] == "kill"


def test_review_round_max_two() -> None:
    client = MagicMock()
    with patch(
        "research_engine.service.dbrec.fetch_research_hypothesis",
        return_value={
            "id": "h1",
            "program_id": "p1",
            "economic_rationale": "a" * 100,
            "mechanism_json": {"primary_mechanism": "x" * 30},
            "feature_definition_json": {},
            "hypothesis_title": "T",
            "review_rounds_completed": 2,
        },
    ):
        out = run_review_round(client, hypothesis_id="h1")
    assert out.get("ok") is False
    assert out.get("error") == "max_review_rounds_reached"


def test_dossier_contains_disagreement_and_unknowns() -> None:
    dossier = build_dossier(
        program={"research_question": "Q?", "title": "T"},
        hypotheses=[
            {
                "id": "h1",
                "hypothesis_title": "H",
                "status": "sandboxed",
                "economic_rationale": "E",
            }
        ],
        reviews=[],
        referee_decisions=[
            {
                "hypothesis_id": "h1",
                "final_decision": "sandbox",
                "disagreement_json": {"unresolved_objections": ["obj_a"]},
            }
        ],
        residual_links=[
            {
                "hypothesis_id": "h1",
                "residual_triage_bucket": "unresolved_residual",
            }
        ],
    )
    assert "obj_a" in dossier["explicit_unknowns"]
    assert dossier["hypotheses_dossier"][0]["residual_links"]


def test_state_change_runner_does_not_import_research_engine() -> None:
    p = Path(__file__).resolve().parents[1] / "state_change" / "runner.py"
    text = p.read_text(encoding="utf-8")
    assert "research_engine" not in text


def test_phase14_cli_registered() -> None:
    from main import build_parser

    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    assert "create-research-program" in names
    assert "export-research-dossier" in names
