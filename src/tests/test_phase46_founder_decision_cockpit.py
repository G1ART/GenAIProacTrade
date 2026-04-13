"""DB-free Phase 46: read model, governed pitch, drill-down, ledgers, UI contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase46.alert_ledger import append_alert, list_alerts, load_alert_ledger
from phase46.decision_trace_ledger import append_decision, list_decisions
from phase46.drilldown import VALID_LAYERS, render_drilldown
from phase46.orchestrator import run_phase46_founder_decision_cockpit
from phase46.read_model import build_founder_read_model
from phase46.representative_agent import assert_pitch_governed, build_representative_pitch
from phase46.ui_contract import build_ui_surface_contract


def _minimal_p45() -> dict:
    return {
        "authoritative_resolution": {
            "authoritative_phase": "phase44_claim_narrowing_truthfulness",
            "authoritative_recommendation": "narrow_claims_document_proxy_limits_operator_closeout_v1",
            "authoritative_rationale": "Close out under truthfulness.",
            "superseded_recommendations": [],
        },
        "canonical_closeout": {
            "cohort": {"row_count": 1, "rows": [{"symbol": "TST", "cik": "1", "signal_available_date": "2025-01-01"}]},
            "what_changed": [{"detail": "Sector diagnosis refined."}],
            "what_did_not_change": [{"detail": "Filing aggregate unchanged."}],
        },
        "current_closeout_status": {"current_closeout_status": "closed_pending_new_evidence"},
        "future_reopen_protocol": {"future_reopen_allowed_with_named_source": True},
        "phase46": {
            "phase46_recommendation": "hold_closeout_until_named_new_source_or_new_evidence_v1",
            "rationale": "Hold.",
        },
    }


def _minimal_p44() -> dict:
    return {
        "gate_after": {
            "gate_status": "deferred",
            "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
        },
        "phase44_truthfulness_assessment": {
            "material_falsifier_improvement": False,
            "optimistic_sector_relabel_only": True,
            "falsifier_usability_improved": False,
        },
        "claim_narrowing": {"cohort_claim_limits": {"claim_status": "narrowed"}},
        "provenance_audit_md_path": "",
        "explanation_v7": {},
    }


def test_read_model_from_phase45_shape() -> None:
    rm = build_founder_read_model(
        phase45_bundle=_minimal_p45(),
        phase44_bundle=_minimal_p44(),
        input_phase45_bundle_path="/tmp/p45.json",
        input_phase44_bundle_path="/tmp/p44.json",
    )
    assert rm["asset_id"] == "research_engine_fixture_cohort_8_row_v1"
    assert rm["decision_status"] == "watching_for_new_evidence"
    assert rm["authoritative_phase"] == "phase44_claim_narrowing_truthfulness"


def test_representative_pitch_governed_no_legacy_phase43_wording() -> None:
    from phase46.cockpit_state import build_cockpit_state

    p45, p44 = _minimal_p45(), _minimal_p44()
    rm = build_founder_read_model(
        phase45_bundle=p45,
        phase44_bundle=p44,
        input_phase45_bundle_path="p45",
        input_phase44_bundle_path="p44",
    )
    cs = build_cockpit_state(founder_read_model=rm, phase45_bundle=p45, phase44_bundle=p44)
    pitch = build_representative_pitch(founder_read_model=rm, cockpit_state=cs, phase45_bundle=p45)
    blob = json.dumps(pitch)
    assert "continue_bounded_falsifier_retest_or_narrow_claims_v1" not in blob
    assert "substrate_backfill_or_narrow_claims_then_retest_v1" not in blob
    assert_pitch_governed(blob)


def test_drilldown_layers_valid() -> None:
    from phase46.cockpit_state import build_cockpit_state

    p45, p44 = _minimal_p45(), _minimal_p44()
    rm = build_founder_read_model(
        phase45_bundle=p45,
        phase44_bundle=p44,
        input_phase45_bundle_path="p45",
        input_phase44_bundle_path="p44",
    )
    cs = build_cockpit_state(founder_read_model=rm, phase45_bundle=p45, phase44_bundle=p44)
    pitch = build_representative_pitch(founder_read_model=rm, cockpit_state=cs, phase45_bundle=p45)
    for layer in VALID_LAYERS:
        d = render_drilldown(
            layer,
            founder_read_model=rm,
            representative_pitch=pitch,
            cockpit_state=cs,
            phase45_bundle=p45,
            phase44_bundle=p44,
        )
        assert d["layer"] == layer
        assert d["governed"] is True
    with pytest.raises(ValueError, match="unknown"):
        render_drilldown(
            "nope",
            founder_read_model=rm,
            representative_pitch=pitch,
            cockpit_state=cs,
            phase45_bundle=p45,
            phase44_bundle=p44,
        )


def test_alert_ledger_append_and_list(tmp_path: Path) -> None:
    p = tmp_path / "alerts.json"
    append_alert(
        p,
        asset_id="x",
        alert_class="test",
        message_summary="hello",
        triggering_source_artifact="bundle",
        requires_attention=True,
    )
    assert len(list_alerts(p)) == 1
    data = load_alert_ledger(p)
    assert data["alerts"][0]["status"] == "open"
    assert data["alerts"][0].get("alert_id")


def test_decision_ledger_append_and_list(tmp_path: Path) -> None:
    p = tmp_path / "dec.json"
    append_decision(
        p,
        asset_id="x",
        decision_type="hold",
        founder_note="wait",
        linked_message_summary="m",
        linked_authoritative_artifact="p45",
        linked_research_provenance="p44",
    )
    assert len(list_decisions(p)) == 1


def test_closeout_maps_to_watching_status() -> None:
    rm = build_founder_read_model(
        phase45_bundle=_minimal_p45(),
        phase44_bundle=_minimal_p44(),
        input_phase45_bundle_path="a",
        input_phase44_bundle_path="b",
    )
    assert rm["closeout_status"] == "closed_pending_new_evidence"
    assert rm["decision_status"] == "watching_for_new_evidence"


def test_ui_contract_sections() -> None:
    c = build_ui_surface_contract()
    assert "asset_list_cards" in c
    assert "drilldown_panels" in c
    assert "alert_feed" in c
    assert "decision_ledger_feed" in c
    assert len(c["drilldown_panels"]["layers"]) == 6


def test_operator_bundles_smoke(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p45p = repo / "docs/operator_closeout/phase45_canonical_closeout_bundle.json"
    p44p = repo / "docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json"
    if not p45p.is_file() or not p44p.is_file():
        pytest.skip("operator bundles missing")
    p45c = tmp_path / "p45.json"
    p44c = tmp_path / "p44.json"
    p45c.write_text(p45p.read_text(encoding="utf-8"), encoding="utf-8")
    p44c.write_text(p44p.read_text(encoding="utf-8"), encoding="utf-8")
    out = run_phase46_founder_decision_cockpit(
        phase45_bundle_in=str(p45c),
        phase44_bundle_in=str(p44c),
        repo_root=tmp_path,
    )
    assert out["ok"] is True
    assert out["phase"] == "phase46_founder_decision_cockpit"
    assert "founder_read_model" in out
    assert "ui_surface_contract" in out
    assert out["phase47"]["phase47_recommendation"]
    pitch = out["representative_pitch"]
    blob = json.dumps(pitch)
    assert "continue_bounded_falsifier_retest_or_narrow_claims_v1" not in blob
