"""Phase 39 — no DB; bundle shape, lifecycle, gate category, idempotent adversarial merge."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from phase39.adversarial_batch import merge_adversarial_reviews
from phase39.orchestrator import run_phase39_hypothesis_family_expansion
from phase39.promotion_gate_phase39 import BLOCK_INTEGRITY, build_promotion_gate_phase39


def test_build_promotion_gate_integrity_when_leakage_fails() -> None:
    g = build_promotion_gate_phase39(
        prior_gate={},
        hypotheses=[{"hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1", "status": "challenged"}],
        adversarial_reviews=[],
        pit_leakage_passed=False,
        primary_adversarial_status="deferred_with_evidence_reinforces_baseline_mismatch",
    )
    assert g["primary_block_category"] == BLOCK_INTEGRITY
    assert g["gate_status"] == "blocked"


def test_merge_adversarial_idempotent(tmp_path: Path) -> None:
    existing = [
        {
            "review_id": "lineage-1",
            "hypothesis_id": "hyp_pit_join_key_mismatch_as_of_boundary_v1",
            "reviewer_stance": "data_lineage_auditor",
        }
    ]
    m1 = merge_adversarial_reviews(list(existing), lineage_auditor_review_id="lineage-1")
    m2 = merge_adversarial_reviews(list(m1), lineage_auditor_review_id="lineage-1")
    assert len(m1) == len(m2) == 4


def test_phase39_orchestrator_writes_artifacts(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    p38 = root / "docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json"
    if not p38.is_file():
        pytest.skip("phase38 bundle not present")
    rdir = tmp_path / "research_engine"
    rdir.mkdir(parents=True)
    shutil.copy(root / "data/research_engine/hypotheses_v1.json", rdir / "hypotheses_v1.json")
    shutil.copy(root / "data/research_engine/adversarial_reviews_v1.json", rdir / "adversarial_reviews_v1.json")
    shutil.copy(root / "data/research_engine/promotion_gate_v1.json", rdir / "promotion_gate_v1.json")

    expl = tmp_path / "phase39_explanation_v2.md"
    bundle = run_phase39_hypothesis_family_expansion(
        phase38_bundle_in=str(p38),
        research_data_dir=str(rdir),
        explanation_out=str(expl),
        gate_history_filename="promotion_gate_history_v1.json",
    )

    assert bundle["ok"] is True
    assert bundle["hypothesis_family_count"] >= 5
    assert "challenged" in (bundle.get("lifecycle_status_distribution") or {})
    assert "skeptical_fundamental" in (bundle.get("adversarial_review_count_by_stance") or {})
    assert bundle.get("promotion_gate_primary_block_category") == "deferred_pending_more_hypothesis_coverage"
    assert "phase40_recommendation" in (bundle.get("phase40") or {})

    hyps = json.loads((rdir / "hypotheses_v1.json").read_text(encoding="utf-8"))
    primary = next(h for h in hyps if h["hypothesis_id"] == "hyp_pit_join_key_mismatch_as_of_boundary_v1")
    assert primary["status"] == "challenged"
    assert primary.get("lifecycle_transitions")

    assert expl.is_file()
    hist = json.loads((rdir / "promotion_gate_history_v1.json").read_text(encoding="utf-8"))
    assert isinstance(hist, list) and len(hist) >= 1
