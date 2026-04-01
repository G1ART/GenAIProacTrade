from __future__ import annotations

from factors.prior_period import (
    find_prior_snapshot,
    index_snapshots_by_period,
    normalize_fiscal_period,
    prior_fiscal_period,
)


def test_prior_fiscal_q1_cross_year() -> None:
    assert prior_fiscal_period(2026, "Q1") == (2025, "Q4")


def test_prior_fiscal_q2() -> None:
    assert prior_fiscal_period(2026, "Q2") == (2026, "Q1")


def test_prior_fiscal_fy() -> None:
    assert prior_fiscal_period(2026, "FY") == (2025, "FY")


def test_prior_unknown_period() -> None:
    assert prior_fiscal_period(2026, "UNSPECIFIED") is None


def test_find_prior_snapshot() -> None:
    snaps = [
        {"fiscal_year": 2025, "fiscal_period": "Q4", "accession_no": "a1", "filed_at": "2025-11-01"},
        {"fiscal_year": 2026, "fiscal_period": "Q1", "accession_no": "a2", "filed_at": "2026-02-01"},
    ]
    cur = snaps[1]
    assert find_prior_snapshot(cur, snaps)["accession_no"] == "a1"


def test_index_multiple_accession_same_period_picks_latest_filed() -> None:
    rows = [
        {"fiscal_year": 2026, "fiscal_period": "Q1", "accession_no": "old", "filed_at": "2026-01-01"},
        {"fiscal_year": 2026, "fiscal_period": "Q1", "accession_no": "new", "filed_at": "2026-02-01"},
    ]
    idx = index_snapshots_by_period(rows)
    assert idx[(2026, "Q1")]["accession_no"] == "new"


def test_normalize_fp() -> None:
    assert normalize_fiscal_period("q2") == "Q2"
