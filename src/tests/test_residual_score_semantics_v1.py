"""Pragmatic Brain Absorption v1 — Milestone B.

Locks the `residual_score_semantics_v1` contract in two places: the spectrum
row builder (which must populate the new optional fields deterministically)
and the MessageObjectV1 layer (which must forward them when present without
regressing Product Spec §6.4 required fields).
"""

from __future__ import annotations

from metis_brain.message_object_v1 import build_message_object_v1_for_today_row
from metis_brain.spectrum_rows_from_validation_v1 import (
    RESIDUAL_SCORE_SEMANTICS_VERSION,
    _RECHECK_CADENCE_BY_BUNDLE_HORIZON,
    _invalidation_hint_for_row,
    build_spectrum_rows_from_validation,
)


def test_recheck_cadence_covers_all_bundle_horizons() -> None:
    assert set(_RECHECK_CADENCE_BY_BUNDLE_HORIZON.keys()) == {
        "short",
        "medium",
        "medium_long",
        "long",
    }


def test_invalidation_hint_priority_pit_fail() -> None:
    hint = _invalidation_hint_for_row(
        pit_pass=False, confidence_band="high", spectrum_position=0.1
    )
    assert hint == "factor_validation_pit_fail"


def test_invalidation_hint_priority_low_confidence() -> None:
    hint = _invalidation_hint_for_row(
        pit_pass=True, confidence_band="low", spectrum_position=0.1
    )
    assert hint == "confidence_band_drops_to_low"


def test_invalidation_hint_midline_cross() -> None:
    hint = _invalidation_hint_for_row(
        pit_pass=True, confidence_band="high", spectrum_position=0.5
    )
    assert hint == "spectrum_position_crosses_midline"


def test_invalidation_hint_default_horizon_reverse_sign() -> None:
    hint = _invalidation_hint_for_row(
        pit_pass=True, confidence_band="high", spectrum_position=0.05
    )
    assert hint == "horizon_returns_reverse_sign"


def test_spectrum_rows_carry_residual_semantics_fields() -> None:
    summary_row = {
        "spearman_rank_corr": 0.2,
        "sample_count": 120,
        "valid_factor_count": 100,
        "pit_pass": True,
    }
    joined_rows = [
        {"symbol": "AAA", "accruals": 0.01, "fiscal_year": 2024, "fiscal_period": "Q1", "accession_no": "a1"},
        {"symbol": "BBB", "accruals": 0.02, "fiscal_year": 2024, "fiscal_period": "Q1", "accession_no": "b1"},
        {"symbol": "CCC", "accruals": 0.03, "fiscal_year": 2024, "fiscal_period": "Q1", "accession_no": "c1"},
    ]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="accruals",
        horizon_type="next_quarter",
        summary_row=summary_row,
        joined_rows=joined_rows,
    )
    assert rows, "spectrum rows should be synthesized from joined rows"
    for r in rows:
        assert r["residual_score_semantics_version"] == RESIDUAL_SCORE_SEMANTICS_VERSION
        assert r["recheck_cadence"] == "quarterly_after_new_filing_or_63_trading_days"
        assert r["invalidation_hint"] in {
            "factor_validation_pit_fail",
            "confidence_band_drops_to_low",
            "spectrum_position_crosses_midline",
            "horizon_returns_reverse_sign",
        }


def test_message_object_forwards_residual_fields_when_present() -> None:
    row = {
        "asset_id": "XYZ",
        "spectrum_position": 0.8,
        "residual_score_semantics_version": RESIDUAL_SCORE_SEMANTICS_VERSION,
        "invalidation_hint": "horizon_returns_reverse_sign",
        "recheck_cadence": "quarterly_after_new_filing_or_63_trading_days",
    }
    msg = build_message_object_v1_for_today_row(
        row=row,
        horizon="medium",
        lang="en",
        rationale_summary="Latest quarterly factor rank refreshed.",
        what_changed_plain="rank moved up",
        confidence_band="medium",
        linked_registry_entry_id="reg_medium_demo_v0",
        linked_artifact_id="art_medium_demo_v0",
    )
    assert msg.residual_score_semantics_version == RESIDUAL_SCORE_SEMANTICS_VERSION
    assert msg.invalidation_hint == "horizon_returns_reverse_sign"
    assert msg.recheck_cadence == "quarterly_after_new_filing_or_63_trading_days"
    # Product Spec §6.4 required fields still present.
    assert msg.headline and msg.confidence_band == "medium"


def test_message_object_defaults_residual_fields_to_empty() -> None:
    row = {"asset_id": "ABC", "spectrum_position": 0.1}
    msg = build_message_object_v1_for_today_row(
        row=row,
        horizon="short",
        lang="en",
        rationale_summary="Factor rank refreshed.",
        what_changed_plain="—",
        confidence_band="low",
        linked_registry_entry_id="reg_short_demo_v0",
        linked_artifact_id="art_short_demo_v0",
    )
    assert msg.residual_score_semantics_version == ""
    assert msg.invalidation_hint == ""
    assert msg.recheck_cadence == ""
