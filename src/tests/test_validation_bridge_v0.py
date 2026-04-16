"""Metis validation → promotion gate bridge (minimal contract)."""

from __future__ import annotations

from metis_brain.validation_bridge_v0 import promotion_gate_from_validation_summary


def test_promotion_gate_from_validation_summary_defaults() -> None:
    g = promotion_gate_from_validation_summary(
        artifact_id="art_x",
        evaluation_run_id="run_001",
        summary={"pit_pass": True, "coverage_pass": True, "monotonicity_pass": True},
    )
    assert g.artifact_id == "art_x"
    assert g.evaluation_run_id == "run_001"
    assert g.pit_pass and g.coverage_pass and g.monotonicity_pass
    assert g.approved_by_rule == "factor_validation_summary:v0"
    assert g.challenger_or_active == "active"


def test_promotion_gate_aliases_and_role() -> None:
    g = promotion_gate_from_validation_summary(
        artifact_id="a1",
        evaluation_run_id="r2",
        summary={
            "pit_ok": True,
            "coverage_ok": False,
            "monotonicity_ok": True,
            "challenger_or_active": "challenger",
            "approved_by_rule": "spread_quintile_rule:v1",
            "reasons": "coverage_gap_on_tail_names",
        },
    )
    assert g.pit_pass and not g.coverage_pass and g.monotonicity_pass
    assert g.challenger_or_active == "challenger"
    assert g.approved_by_rule == "spread_quintile_rule:v1"
    assert "coverage_gap" in g.reasons
