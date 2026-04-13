"""DB-free Phase 45: precedence, closeout, reopen protocol, Phase 46 default."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase45.authoritative_resolver import resolve_authoritative_recommendation
from phase45.closeout_package import build_canonical_closeout
from phase45.orchestrator import run_phase45_operator_closeout_and_reopen_protocol
from phase45.phase46_recommend import recommend_phase46
from phase45.reopen_protocol import build_future_reopen_protocol


def _phase44_min() -> dict:
    return {
        "phase45": {
            "phase45_recommendation": "narrow_claims_document_proxy_limits_operator_closeout_v1",
            "rationale": "closeout",
        },
        "scorecard_phase42_supabase_before": {
            "filing_blocker_distribution": {"no_10k_10q_rows_for_cik": 7, "only_post_signal_filings_available": 1},
            "sector_blocker_distribution": {"no_market_metadata_row_for_symbol": 8},
        },
        "scorecard_phase43_after": {
            "filing_blocker_distribution": {"no_10k_10q_rows_for_cik": 7, "only_post_signal_filings_available": 1},
            "sector_blocker_distribution": {"sector_field_blank_on_metadata_row": 8},
        },
        "gate_after": {
            "gate_status": "deferred",
            "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
        },
        "phase44_truthfulness_assessment": {
            "material_falsifier_improvement": False,
            "filing_distribution_changed": False,
            "falsifier_usability_improved": False,
            "gate_materially_improved": False,
            "discrimination_rollups_improved": False,
        },
        "claim_narrowing": {
            "family_claim_limits": {
                "f1": {
                    "unsupported_scope": "unsupported filing claim",
                },
            },
            "cohort_claim_limits": {"unsupported_scope": "unsupported cohort claim"},
            "bounded_retry_eligibility": "x",
        },
        "retry_eligibility": {
            "phase43_paths_already_used": {"filing": "bounded_run_sample_ingest_per_cik", "sector": "yahoo_chart"},
        },
    }


def _phase43_min() -> dict:
    return {
        "phase44": {
            "phase44_recommendation": "continue_bounded_falsifier_retest_or_narrow_claims_v1",
            "rationale": "optimistic legacy",
        },
        "stable_run_digest_before": "aaa",
        "stable_run_digest_after": "bbb",
        "target_cohort": [
            {
                "symbol": "X",
                "cik": "1",
                "signal_available_date": "2025-01-01",
            }
        ],
        "backfill_actions": {
            "filing": {"repair": "bounded_run_sample_ingest_per_cik"},
            "sector": {"provider": "yahoo_chart"},
        },
        "phase42_rerun_after_backfill": {
            "phase43": {
                "phase43_recommendation": "substrate_backfill_or_narrow_claims_then_retest_v1",
                "rationale": "nested",
            }
        },
    }


def test_phase44_supersedes_phase43_legacy_optimistic_wording() -> None:
    ar = resolve_authoritative_recommendation(
        phase43_bundle=_phase43_min(),
        phase44_bundle=_phase44_min(),
    )
    assert ar["authoritative_phase"] == "phase44_claim_narrowing_truthfulness"
    assert ar["authoritative_recommendation"] == "narrow_claims_document_proxy_limits_operator_closeout_v1"
    paths = {s.get("field_path") for s in ar["superseded_recommendations"]}
    assert "phase44.phase44_recommendation" in paths


def test_canonical_closeout_unchanged_filing_gate_sector_relabel_only() -> None:
    p43, p44 = _phase43_min(), _phase44_min()
    ar = resolve_authoritative_recommendation(phase43_bundle=p43, phase44_bundle=p44)
    fr = build_future_reopen_protocol(phase44_bundle=p44)
    cc = build_canonical_closeout(
        phase43_bundle=p43,
        phase44_bundle=p44,
        authoritative_resolution=ar,
        future_reopen_protocol=fr,
    )
    assert cc["cohort"]["row_count"] == 1
    assert cc["what_did_not_change"][0]["axis"] == "filing_scorecard"
    assert cc["what_did_not_change"][0]["evidence"]["filing_distribution_changed"] is False
    gate_block = next(x for x in cc["what_did_not_change"] if x["axis"] == "promotion_gate")
    assert gate_block["evidence"]["gate_materially_improved"] is False
    ch = cc["what_changed"][0]
    assert ch["axis"] == "sector_diagnosis"
    assert "blank" in ch["detail"].lower() or "sector_field_blank" in ch["detail"]


def test_reopen_protocol_requires_named_declaration_fields() -> None:
    fr = build_future_reopen_protocol(phase44_bundle=_phase44_min())
    req = fr["required_operator_declaration_fields"]
    assert any("named" in x.lower() for x in req)
    assert fr["future_reopen_allowed_with_named_source"] is True


def test_reopen_protocol_forbids_broad_public_core() -> None:
    fr = build_future_reopen_protocol(phase44_bundle=_phase44_min())
    forbidden = " ".join(fr["forbidden_reopen_axes"]).lower()
    assert "broad" in forbidden or "public" in forbidden


def test_phase46_default_hold_closeout() -> None:
    p46 = recommend_phase46(operator_registered_new_named_source=False)
    assert p46["phase46_recommendation"] == "hold_closeout_until_named_new_source_or_new_evidence_v1"


def test_phase46_alternate_when_registration_flag() -> None:
    p46 = recommend_phase46(operator_registered_new_named_source=True)
    assert p46["phase46_recommendation"] == "register_new_source_then_authorize_one_bounded_reopen_v1"


def test_operator_bundles_smoke(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    p44p = repo / "docs/operator_closeout/phase44_claim_narrowing_truthfulness_bundle.json"
    p43p = repo / "docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json"
    if not p44p.is_file() or not p43p.is_file():
        pytest.skip("operator closeout bundles missing")
    p44c = tmp_path / "p44.json"
    p43c = tmp_path / "p43.json"
    p44c.write_text(p44p.read_text(encoding="utf-8"), encoding="utf-8")
    p43c.write_text(p43p.read_text(encoding="utf-8"), encoding="utf-8")
    out = run_phase45_operator_closeout_and_reopen_protocol(
        phase44_bundle_in=str(p44c),
        phase43_bundle_in=str(p43c),
    )
    assert out["ok"] is True
    assert out["phase"] == "phase45_operator_closeout_and_reopen_protocol"
    assert out["current_closeout_status"]["current_closeout_status"] == "closed_pending_new_evidence"
    assert out["phase46"]["phase46_recommendation"].startswith("hold_closeout")
    json.dumps(out)
