"""Phase 27: registry/metadata/forward maturity/PIT + 경계."""

from __future__ import annotations

import importlib
import inspect
from datetime import date
from unittest.mock import MagicMock, patch

from targeted_backfill.constants import (
    CALENDAR_DAYS_1Q_MATURITY_PROXY,
    PIT_ALIGNMENT_SLACK_CALENDAR_DAYS,
)
from targeted_backfill.forward_maturity import classify_forward_gap_maturity_row
from targeted_backfill.phase28_recommend import (
    PHASE28_CONTINUE_BACKFILL,
    PHASE28_QUALITY,
    PHASE28_RERUN_15_16,
    recommend_phase28_branch,
)
from targeted_backfill.market_metadata_gaps import _classify_joined_metadata_row
from targeted_backfill.state_change_pit import classify_state_change_pit_row
from targeted_backfill.validation_registry import _classify_one


def test_metadata_gap_missing_registry_link() -> None:
    client = MagicMock()
    b = _classify_joined_metadata_row(
        {"symbol": "A", "signal_available_date": "2020-01-15"},
        registry_by_sym={},
        meta_by_sym={},
        client=client,
    )
    assert b == "missing_market_symbol_registry_link"


def test_validation_registry_bucket_factor_missing() -> None:
    b = _classify_one(
        "AAA",
        cik_by_symbol={"AAA": "1"},
        registry_by_sym={
            "AAA": {"symbol": "AAA", "cik": "0000000001"},
        },
        mem_cik_raw="1",
        registry_syms_by_cik={},
        issuer_ciks_norm_present={"0000000001"},
        ciks_with_factor=set(),
        val_by_cik={},
        canonical_for_cik={"0000000001": "AAA"},
    )
    assert b == "factor_panel_missing_for_resolved_cik"


def test_validation_registry_normalization_mismatch() -> None:
    b = _classify_one(
        "AAA",
        cik_by_symbol={"AAA": "1"},
        registry_by_sym={"AAA": {"symbol": "AAA", "cik": "0000000001"}},
        mem_cik_raw="1",
        registry_syms_by_cik={},
        issuer_ciks_norm_present={"0000000001"},
        ciks_with_factor={"0000000001"},
        val_by_cik={"0000000001": [{"symbol": "BBB", "cik": "0000000001"}]},
        canonical_for_cik={"0000000001": "BBB"},
    )
    assert b == "symbol_normalization_mismatch"


def test_forward_maturity_not_yet_matured() -> None:
    client = MagicMock()
    sig = "2026-01-15"
    ev = date.fromisoformat("2026-02-01")
    out = classify_forward_gap_maturity_row(
        symbol="ZZZ",
        signal_date_raw=sig,
        eval_date=ev,
        client=client,
    )
    assert out["bucket"] == "not_yet_matured_for_1q_horizon"
    assert out["calendar_days_proxy"] == CALENDAR_DAYS_1Q_MATURITY_PROXY


@patch("targeted_backfill.forward_maturity.dbrec.fetch_silver_prices_for_symbol_range", return_value=[])
def test_forward_matured_no_prices(_mock_fetch: MagicMock) -> None:
    client = MagicMock()
    sig = "2020-01-15"
    ev = date.fromisoformat("2025-01-01")
    out = classify_forward_gap_maturity_row(
        symbol="ZZZ",
        signal_date_raw=sig,
        eval_date=ev,
        client=client,
    )
    assert out["bucket"] == "symbol_price_link_missing"


def test_pit_alignment_vs_window() -> None:
    c1 = classify_state_change_pit_row(
        symbol="A",
        cik="1",
        signal_date_raw="2020-06-01",
        earliest_sc_raw="2020-06-03",
    )
    assert c1["pit_bucket"] == "signal_to_state_change_alignment_gap"
    assert c1["delta_calendar_days"] == 2
    c2 = classify_state_change_pit_row(
        symbol="A",
        cik="1",
        signal_date_raw="2020-06-01",
        earliest_sc_raw="2020-07-15",
    )
    assert c2["pit_bucket"] == "state_change_history_window_too_short"
    c3 = classify_state_change_pit_row(
        symbol="A",
        cik="1",
        signal_date_raw="2020-06-01",
        earliest_sc_raw="2021-01-01",
    )
    assert c3["pit_bucket"] == "no_pre_signal_state_change_asof"


def test_pit_constants_ordering() -> None:
    assert PIT_ALIGNMENT_SLACK_CALENDAR_DAYS < 120


def test_phase28_rerun_gate() -> None:
    r = recommend_phase28_branch(
        recommend_rerun_phase15=True,
        recommend_rerun_phase16=False,
        true_repairable_forward=0,
        joined_metadata_flagged=0,
        pit_backfill_candidates=0,
        registry_blocker_total_count=0,
        thin_input_share_after=1.0,
    )
    assert r["phase28_recommendation"] == PHASE28_RERUN_15_16


def test_phase28_continue_backfill() -> None:
    r = recommend_phase28_branch(
        recommend_rerun_phase15=False,
        recommend_rerun_phase16=False,
        true_repairable_forward=3,
        joined_metadata_flagged=0,
        pit_backfill_candidates=0,
        registry_blocker_total_count=0,
        thin_input_share_after=1.0,
    )
    assert r["phase28_recommendation"] == PHASE28_CONTINUE_BACKFILL


def test_phase28_quality_when_thin_persists() -> None:
    r = recommend_phase28_branch(
        recommend_rerun_phase15=False,
        recommend_rerun_phase16=False,
        true_repairable_forward=0,
        joined_metadata_flagged=0,
        pit_backfill_candidates=0,
        registry_blocker_total_count=0,
        thin_input_share_after=1.0,
    )
    assert r["phase28_recommendation"] == PHASE28_QUALITY


def test_targeted_backfill_no_premium_or_production_wiring() -> None:
    forbidden = (
        "hypothesis_registry",
        "research_engine",
        "validation_campaign",
        "open_targeted_premium_discovery",
        "public_repair_iteration",
        "public_repair_campaign",
    )
    for mod_name in (
        "targeted_backfill",
        "targeted_backfill.validation_registry",
        "targeted_backfill.market_metadata_gaps",
        "targeted_backfill.forward_maturity",
        "targeted_backfill.state_change_pit",
        "targeted_backfill.review",
        "targeted_backfill.phase28_recommend",
        "targeted_backfill.repair_closeout",
    ):
        m = importlib.import_module(mod_name)
        src = inspect.getsource(m)
        for tok in forbidden:
            assert tok not in src, f"{mod_name} must not reference {tok}"
