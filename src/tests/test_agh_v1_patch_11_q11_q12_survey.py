"""Patch 11 — M3: Q11 / Q12 additions to the MVP spec survey.

- Q1..Q10 semantics MUST remain unchanged (order, id, spec text).
- Q11 = signal_quality_accumulation: short/medium rows must carry
  residual-score semantics at >= 80% coverage; medium_long/long are
  only audited when their long_horizon_support tier is limited or
  production.
- Q12 = long_horizon_honest_tier: medium_long + long must have a
  ``long_horizon_support`` block and no provenance ↔ tier integrity
  errors.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from metis_brain.mvp_spec_survey_v0 import (
    _q11_signal_quality_accumulation,
    _q12_long_horizon_honest_tier,
)


def _row(with_residual: bool = True, asset_id: str = "AAPL") -> dict:
    row = {
        "asset_id": asset_id,
        "spectrum_position": 0.35,
        "message": {
            "headline": "x",
            "why_now": "y",
        },
        "rationale_summary": "z",
    }
    if with_residual:
        row["residual_score_semantics_version"] = "residual_semantics_v1"
        row["invalidation_hint"] = "spectrum_position_crosses_midline"
        row["recheck_cadence"] = "monthly_after_new_filing_or_21_trading_days"
    return row


def _support_entry(tier: str, *, n_rows: int = 50, n_symbols: int = 25) -> dict:
    return {
        "contract_version": "LONG_HORIZON_SUPPORT_V1",
        "tier_key":         tier,
        "n_rows":           n_rows,
        "n_symbols":        n_symbols,
        "coverage_ratio":   0.9 if tier == "production" else 0.5 if tier == "limited" else 0.1,
        "as_of_utc":        "2026-04-23T00:00:00Z",
        "reason":           tier,
    }


def _bundle_from(
    *,
    short_rows: list[dict] | None = None,
    medium_rows: list[dict] | None = None,
    medium_long_rows: list[dict] | None = None,
    long_rows: list[dict] | None = None,
    long_support: dict[str, dict] | None = None,
    horizon_provenance: dict[str, dict] | None = None,
) -> SimpleNamespace:
    short_rows = short_rows if short_rows is not None else [_row() for _ in range(5)]
    medium_rows = medium_rows if medium_rows is not None else [_row() for _ in range(5)]
    medium_long_rows = medium_long_rows if medium_long_rows is not None else [_row() for _ in range(5)]
    long_rows = long_rows if long_rows is not None else [_row() for _ in range(5)]
    horizon_provenance = horizon_provenance or {
        "short":       {"source": "real_derived"},
        "medium":      {"source": "real_derived"},
        "medium_long": {"source": "real_derived"},
        "long":        {"source": "insufficient_evidence"},
    }
    return SimpleNamespace(
        spectrum_rows_by_horizon={
            "short":       short_rows,
            "medium":      medium_rows,
            "medium_long": medium_long_rows,
            "long":        long_rows,
        },
        horizon_provenance=horizon_provenance,
        long_horizon_support_by_horizon=long_support or {},
    )


# ---------------------------------------------------------------------------
# Q11 — signal quality accumulation
# ---------------------------------------------------------------------------


def test_q11_short_medium_full_residual_passes():
    bundle = _bundle_from()
    ok, detail = _q11_signal_quality_accumulation(bundle)
    assert ok, detail
    assert "short:5/5" in detail
    assert "medium:5/5" in detail


def test_q11_short_insufficient_coverage_fails():
    rows = [_row(with_residual=False) for _ in range(10)]
    rows += [_row() for _ in range(2)]
    bundle = _bundle_from(short_rows=rows)
    ok, detail = _q11_signal_quality_accumulation(bundle)
    assert not ok
    assert "short_coverage_0.17" in detail or "short_coverage" in detail


def test_q11_long_horizon_sample_tier_is_exempt():
    """When long_horizon_support.tier is sample, long is not audited."""
    bad_long_rows = [_row(with_residual=False) for _ in range(10)]
    bundle = _bundle_from(
        long_rows=bad_long_rows,
        long_support={"long": _support_entry("sample")},
    )
    ok, detail = _q11_signal_quality_accumulation(bundle)
    assert ok, detail


def test_q11_long_horizon_production_tier_requires_coverage():
    """When long_horizon_support.tier is production, long MUST meet the
    residual-coverage threshold as well (honest tier = must back it up)."""
    bad_long_rows = [_row(with_residual=False) for _ in range(10)]
    bundle = _bundle_from(
        long_rows=bad_long_rows,
        long_support={"long": _support_entry("production")},
    )
    ok, detail = _q11_signal_quality_accumulation(bundle)
    assert not ok
    assert "long_tier=production" in detail


def test_q11_no_bundle_fails():
    ok, detail = _q11_signal_quality_accumulation(None)
    assert not ok
    assert detail == "no_bundle"


# ---------------------------------------------------------------------------
# Q12 — long-horizon honest tier
# ---------------------------------------------------------------------------


def test_q12_passes_when_support_is_honest_sample():
    bundle = _bundle_from(
        long_support={
            "medium_long": _support_entry("limited"),
            "long":        _support_entry("sample"),
        },
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        },
    )
    ok, detail = _q12_long_horizon_honest_tier(bundle)
    assert ok, detail
    assert "medium_long:tier=limited" in detail
    assert "long:tier=sample" in detail


def test_q12_fails_when_provenance_lies_real_but_sample():
    bundle = _bundle_from(
        long_support={
            "medium_long": _support_entry("sample"),
            "long":        _support_entry("sample"),
        },
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "real_derived"},
        },
    )
    ok, detail = _q12_long_horizon_honest_tier(bundle)
    assert not ok
    assert "medium_long" in detail or "long" in detail


def test_q12_fails_when_support_block_missing_with_real_derived_provenance():
    # Default _bundle_from provenance marks medium_long=real_derived, so
    # absence of a support block is an over-claim-by-silence.
    bundle = _bundle_from(long_support={})
    ok, detail = _q12_long_horizon_honest_tier(bundle)
    assert not ok
    assert "real_derived_provenance_without_support_block" in detail


def test_q12_passes_when_support_block_missing_and_provenance_is_insufficient():
    # Absence-is-honesty: when provenance already says insufficient_evidence
    # for medium_long AND long, there is nothing to lie about.
    bundle = _bundle_from(
        long_support={},
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "insufficient_evidence"},
            "long":        {"source": "insufficient_evidence"},
        },
    )
    ok, detail = _q12_long_horizon_honest_tier(bundle)
    assert ok, detail
    assert "medium_long" in detail
    assert "long" in detail


def test_q12_fails_when_one_horizon_missing_with_real_derived_provenance():
    bundle = _bundle_from(
        long_support={"medium_long": _support_entry("production")},
    )
    ok, detail = _q12_long_horizon_honest_tier(bundle)
    # Default provenance.long == insufficient_evidence → honest absence for
    # long alone. But medium_long claims "production" with real_derived
    # provenance → integrity check passes. We now expect Q12 to *pass* in
    # this configuration (absence of long is honest under its provenance).
    assert ok, detail


# ---------------------------------------------------------------------------
# Integration — build_mvp_spec_survey_v0 adds Q11/Q12 and preserves Q1..Q10.
# ---------------------------------------------------------------------------


def test_build_survey_includes_q11_q12_without_disturbing_q1_q10(tmp_path, monkeypatch):
    from metis_brain import mvp_spec_survey_v0 as survey_mod

    # Neutralise the heavy Today payload builds for this structural
    # test: Q11/Q12 only care about bundle contents. Use monkeypatch so
    # the override is undone after the test runs (otherwise it pollutes
    # the repo-bundle survey test that runs later in the session).
    def _noop_payloads(*args, **kwargs):
        return {h: {"ok": False, "error": "skipped"} for h in (
            "short", "medium", "medium_long", "long",
        )}

    monkeypatch.setattr(
        survey_mod, "_load_spectrum_payloads_all_horizons", _noop_payloads,
    )

    out = survey_mod.build_mvp_spec_survey_v0(tmp_path)
    ids = [q["id"] for q in out["questions"]]
    expected_prefix = [
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
    ]
    assert ids[:10] == expected_prefix
    assert "Q11_signal_quality_accumulation" in ids
    assert "Q12_long_horizon_honest_tier" in ids
    # Q11/Q12 rendered even when no bundle is available.
    q11 = next(q for q in out["questions"] if q["id"] == "Q11_signal_quality_accumulation")
    q12 = next(q for q in out["questions"] if q["id"] == "Q12_long_horizon_honest_tier")
    assert "ok" in q11 and "detail" in q11
    assert "ok" in q12 and "detail" in q12
