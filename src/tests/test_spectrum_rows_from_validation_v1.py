"""Unit tests for ``metis_brain.spectrum_rows_from_validation_v1``."""

from __future__ import annotations

import pytest

from metis_brain.spectrum_rows_from_validation_v1 import (
    build_spectrum_rows_from_validation,
)


def _summary(**over) -> dict:
    s = {"sample_count": 120, "valid_factor_count": 96, "spearman_rank_corr": -0.2}
    s.update(over)
    return s


def _mk(sym: str, factor: str, val: float, fy: int = 2024, fp: str = "Q4", acc: str = "") -> dict:
    return {
        "symbol": sym,
        factor: val,
        "fiscal_year": fy,
        "fiscal_period": fp,
        "accession_no": acc or f"{sym}-{fy}-{fp}",
    }


def test_empty_input_returns_empty_rows() -> None:
    h, rows = build_spectrum_rows_from_validation(
        factor_name="accruals",
        horizon_type="next_month",
        summary_row=_summary(),
        joined_rows=[],
    )
    assert h == "short"
    assert rows == []


def test_position_monotonic_when_spearman_negative() -> None:
    rows_in = [
        _mk("AAA", "accruals", 0.01),
        _mk("BBB", "accruals", 0.05),
        _mk("CCC", "accruals", 0.10),
        _mk("DDD", "accruals", 0.20),
    ]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="accruals",
        horizon_type="next_month",
        summary_row=_summary(spearman_rank_corr=-0.3),
        joined_rows=rows_in,
    )
    by_sym = {r["asset_id"]: r for r in rows}
    assert by_sym["AAA"]["spectrum_position"] < by_sym["DDD"]["spectrum_position"]


def test_position_inverts_when_spearman_positive() -> None:
    rows_in = [
        _mk("AAA", "gp", 0.01),
        _mk("BBB", "gp", 0.05),
        _mk("CCC", "gp", 0.10),
        _mk("DDD", "gp", 0.20),
    ]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="gp",
        horizon_type="next_month",
        summary_row=_summary(spearman_rank_corr=0.3),
        joined_rows=rows_in,
    )
    by_sym = {r["asset_id"]: r for r in rows}
    assert by_sym["AAA"]["spectrum_position"] > by_sym["DDD"]["spectrum_position"]


def test_one_row_per_symbol_latest_period_wins() -> None:
    rows_in = [
        _mk("AAA", "accruals", 0.01, fy=2022, fp="Q4"),
        _mk("AAA", "accruals", 0.30, fy=2024, fp="Q4"),
    ]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="accruals",
        horizon_type="next_month",
        summary_row=_summary(),
        joined_rows=rows_in,
    )
    assert len(rows) == 1
    assert rows[0]["source_period"]["fiscal_year"] == 2024
    assert rows[0]["source_period"]["factor_value"] == pytest.approx(0.30)


def test_rows_have_required_fields_for_bundle_integrity() -> None:
    rows_in = [_mk("AAA", "acc", 0.02), _mk("BBB", "acc", 0.05)]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="acc",
        horizon_type="next_month",
        summary_row=_summary(),
        joined_rows=rows_in,
    )
    assert len(rows) == 2
    for r in rows:
        assert isinstance(r["asset_id"], str) and r["asset_id"]
        assert 0.0 <= r["spectrum_position"] <= 1.0
        assert r["spectrum_band"] in {"left", "center", "right"}
        assert "rationale_summary" in r


def test_skips_rows_missing_factor_or_symbol() -> None:
    rows_in = [
        _mk("AAA", "acc", 0.01),
        {"symbol": "BBB", "acc": None, "fiscal_year": 2024, "fiscal_period": "Q4", "accession_no": "x"},
        {"symbol": "", "acc": 0.02, "fiscal_year": 2024, "fiscal_period": "Q4", "accession_no": "y"},
    ]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="acc",
        horizon_type="next_month",
        summary_row=_summary(),
        joined_rows=rows_in,
    )
    assert len(rows) == 1
    assert rows[0]["asset_id"] == "AAA"


def test_unsupported_horizon_raises() -> None:
    with pytest.raises(ValueError):
        build_spectrum_rows_from_validation(
            factor_name="acc",
            horizon_type="bogus",
            summary_row=_summary(),
            joined_rows=[],
        )


def test_max_rows_truncates_tail() -> None:
    rows_in = [_mk(f"S{i:03d}", "acc", float(i)) for i in range(20)]
    _, rows = build_spectrum_rows_from_validation(
        factor_name="acc",
        horizon_type="next_month",
        summary_row=_summary(spearman_rank_corr=-0.1),
        joined_rows=rows_in,
        max_rows=5,
    )
    assert len(rows) == 5
