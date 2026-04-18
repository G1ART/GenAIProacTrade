"""Tests for Pragmatic Brain Absorption v1 — Milestone D.

Persona Candidate Harness is **candidate only**: the tests explicitly
assert that no active registry / overlay / validation table surface is
touched by either the builder or the CLI report writer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metis_brain.persona_candidates_v1 import (
    PERSONA_KINDS,
    PersonaCandidatePacketV1,
    build_persona_candidate_packet,
    deterministic_candidate_id,
    write_persona_candidate_report,
)


def _min_valid_spec(**overrides):
    base = {
        "persona": "quant_residual_analyst",
        "thesis_family": "accruals residual tightening",
        "targeted_horizon": "short",
        "targeted_universe": "combined_largecap_research_v1",
        "evidence_refs": [
            {
                "kind": "factor_validation_run",
                "pointer": "factor_validation_run:accruals:next_month:combined_largecap_research_v1",
                "summary": "decile monotonicity + PIT pass",
            }
        ],
        "confidence": 0.5,
        "overlay_recommendation": "",
        "countercase": "may revert on quant flow unwind",
        "gate_eligibility": {"pit": True, "coverage": True, "monotonicity": True},
        "provenance_summary": "Milestone A validation + Milestone B residual semantics",
    }
    base.update(overrides)
    return base


def test_persona_kinds_vocabulary_fixed():
    assert "quant_residual_analyst" in PERSONA_KINDS
    assert "value_reversion_analyst" in PERSONA_KINDS
    assert "non_quant_regime_tracker" in PERSONA_KINDS


def test_build_persona_candidate_packet_happy_path_sets_promotion_note():
    pkt = build_persona_candidate_packet(**_min_valid_spec())
    assert isinstance(pkt, PersonaCandidatePacketV1)
    assert pkt.contract == "METIS_PERSONA_CANDIDATE_PACKET_V1"
    assert pkt.candidate_id.startswith("pcand_")
    assert pkt.persona == "quant_residual_analyst"
    assert "Candidate only" in pkt.promotion_doctrine_note
    assert "active registry" in pkt.promotion_doctrine_note
    assert pkt.created_at_utc


def test_candidate_id_deterministic_per_persona_thesis_slice():
    a = deterministic_candidate_id(
        persona="quant_residual_analyst",
        thesis_family="accruals residual tightening",
        targeted_horizon="short",
        targeted_universe="combined_largecap_research_v1",
    )
    b = deterministic_candidate_id(
        persona="quant_residual_analyst",
        thesis_family="accruals residual tightening",
        targeted_horizon="short",
        targeted_universe="combined_largecap_research_v1",
    )
    c = deterministic_candidate_id(
        persona="quant_residual_analyst",
        thesis_family="accruals residual tightening",
        targeted_horizon="medium",
        targeted_universe="combined_largecap_research_v1",
    )
    assert a == b
    assert a != c


def test_build_rejects_unknown_persona():
    with pytest.raises(ValueError):
        build_persona_candidate_packet(**_min_valid_spec(persona="mystery_analyst"))


def test_build_rejects_confidence_out_of_range():
    with pytest.raises(ValueError):
        build_persona_candidate_packet(**_min_valid_spec(confidence=1.5))
    with pytest.raises(ValueError):
        build_persona_candidate_packet(**_min_valid_spec(confidence=-0.1))


def test_build_rejects_unknown_horizon():
    with pytest.raises(ValueError):
        build_persona_candidate_packet(**_min_valid_spec(targeted_horizon="forever"))


def test_write_report_emits_json_contract(tmp_path: Path):
    packets = [
        build_persona_candidate_packet(**_min_valid_spec()),
        build_persona_candidate_packet(
            **_min_valid_spec(
                persona="value_reversion_analyst",
                thesis_family="gp reversion",
                targeted_horizon="medium",
                confidence=0.3,
            )
        ),
    ]
    out = tmp_path / "persona_candidates.json"
    report = write_persona_candidate_report(packets, out_path=out)
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert report["contract"] == "METIS_PERSONA_CANDIDATES_REPORT_V1"
    assert on_disk["contract"] == report["contract"]
    assert on_disk["packet_count"] == 2
    assert all(p["candidate_id"].startswith("pcand_") for p in on_disk["packets"])
    assert "never" in on_disk["governance_note"] or "diagnostic" in on_disk["governance_note"]


def test_report_writer_never_touches_active_bundle(tmp_path: Path):
    """Harness is candidate-only: writing the report must not create or
    mutate any file under data/mvp besides the explicit --out-json path."""
    mvp_dir = tmp_path / "data" / "mvp"
    mvp_dir.mkdir(parents=True)
    bundle_path = mvp_dir / "metis_brain_bundle_v0.json"
    bundle_path.write_text(
        json.dumps({"sentinel": "untouched"}, ensure_ascii=False),
        encoding="utf-8",
    )

    out = tmp_path / "persona_report.json"
    packets = [build_persona_candidate_packet(**_min_valid_spec())]
    write_persona_candidate_report(packets, out_path=out)

    assert out.is_file()
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == {"sentinel": "untouched"}


def test_gate_eligibility_is_diagnostic_only_not_promotion():
    """Even with all gate_eligibility flags True, the packet is still
    explicitly a candidate, per promotion doctrine."""
    pkt = build_persona_candidate_packet(
        **_min_valid_spec(
            gate_eligibility={
                "pit": True,
                "coverage": True,
                "monotonicity": True,
                "validation_run_present": True,
                "runtime_explainable": True,
            }
        )
    )
    assert pkt.gate_eligibility["pit"] is True
    assert pkt.contract == "METIS_PERSONA_CANDIDATE_PACKET_V1"
    assert "Candidate only" in pkt.promotion_doctrine_note
