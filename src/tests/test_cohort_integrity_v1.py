"""Unit tests for metis_brain.cohort_integrity_v1 (fake Supabase client)."""

from __future__ import annotations

import json
from pathlib import Path

from metis_brain.cohort_integrity_v1 import (
    _cohort_symbols_from_file,
    compute_cohort_integrity_report,
)


# ----------------------------------------------------------------------------
# Fake Supabase client covering issuer_master, factor_market_validation_panels,
# issuer_quarter_factor_panels, factor_validation_runs/summaries.
# ----------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data):
        self._data = data
        self._filters: list[tuple[str, str, object]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_a, **_kw):
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, list(vals)))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = int(n)
        return self

    def execute(self):
        rows = list(self._data)
        for kind, col, val in self._filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif kind == "in":
                rows = [r for r in rows if r.get(col) in set(val)]
        if self._order is not None:
            col, desc = self._order
            rows.sort(key=lambda r: r.get(col) or "", reverse=bool(desc))
        if self._limit is not None:
            rows = rows[: self._limit]
        return _FakeResp(rows)


class _FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name

    def select(self, *a, **kw):
        return _FakeQuery(self._store.get(self._name, [])).select(*a, **kw)


class _FakeClient:
    def __init__(self, **tables):
        self._store = {k: list(v) for k, v in tables.items()}

    def table(self, name):
        return _FakeTable(self._store, name)


def _make_client(tickers_present: int = 10, with_factor: int = 9, with_vpanel: int = 10):
    cohort = [f"T{i:03d}" for i in range(10)]
    issuer_master = [
        {"ticker": cohort[i], "cik": str(10000 + i)}
        for i in range(tickers_present)
    ]
    vpanels = []
    for i in range(with_vpanel):
        vpanels.append(
            {
                "symbol": cohort[i],
                "cik": str(10000 + i),
                "accession_no": f"acc-{i}",
                "factor_version": "v1",
            }
        )
    factor_panels = []
    for i in range(with_factor):
        # join key builder uses cik + accession_no + factor_version
        factor_panels.append(
            {
                "cik": f"{int(10000 + i):010d}",
                "accession_no": f"acc-{i}",
                "factor_version": "v1",
                "fiscal_year": 2024,
                "fiscal_period": "Q4",
                "accruals": 0.01,
            }
        )
    runs = [
        {
            "id": "run-1",
            "status": "completed",
            "completed_at": "2026-04-16T00:00:00Z",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
        }
    ]
    summaries = [
        {
            "id": "s1",
            "run_id": "run-1",
            "factor_name": "accruals",
            "return_basis": "raw",
            "sample_count": 200,
            "valid_factor_count": 180,
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
        }
    ]
    client = _FakeClient(
        issuer_master=issuer_master,
        factor_market_validation_panels=vpanels,
        issuer_quarter_factor_panels=factor_panels,
        factor_validation_runs=runs,
        factor_validation_summaries=summaries,
    )
    return client, cohort


def test_cohort_integrity_all_present_passes() -> None:
    client, cohort = _make_client()
    report = compute_cohort_integrity_report(
        client,
        cohort_symbols=cohort,
        universe="sp500_current",
        factor_name="accruals",
        horizon_type="next_month",
        return_basis="raw",
        min_pass_ratio=0.9,
    )
    assert report["ok"] is True
    assert report["cohort_size"] == 10
    assert report["stages"]["issuer_master"]["resolved_symbol_count"] == 10
    assert report["stages"]["factor_market_validation_panels"]["cik_count"] == 10
    assert report["stages"]["issuer_quarter_factor_panels"]["cik_with_factor_value_count"] == 9
    assert report["headline"]["pass"] is True
    assert report["headline"]["pass_ratio"] == 1.0


def test_cohort_integrity_below_ratio_fails() -> None:
    client, cohort = _make_client(tickers_present=10, with_factor=3, with_vpanel=5)
    report = compute_cohort_integrity_report(
        client,
        cohort_symbols=cohort,
        universe="sp500_current",
        factor_name="accruals",
        horizon_type="next_month",
        return_basis="raw",
        min_pass_ratio=0.9,
    )
    assert report["headline"]["pass"] is False
    assert report["headline"]["pass_numerator_vpanel_ciks"] == 5
    assert report["stages"]["issuer_quarter_factor_panels"]["cik_with_factor_value_count"] == 3
    # Missing-symbol lists are populated so operator sees what is absent.
    assert report["stages"]["factor_market_validation_panels"]["missing_symbols_sample"]


def test_cohort_integrity_missing_from_issuer_master() -> None:
    client, cohort = _make_client(tickers_present=6)
    report = compute_cohort_integrity_report(
        client,
        cohort_symbols=cohort,
        universe="sp500_current",
        factor_name="accruals",
        horizon_type="next_month",
        return_basis="raw",
        min_pass_ratio=0.5,
    )
    assert report["stages"]["issuer_master"]["missing_symbol_count"] == 4
    assert set(report["stages"]["issuer_master"]["missing_symbols_sample"]) == {
        "T006",
        "T007",
        "T008",
        "T009",
    }


def test_cohort_file_reader_accepts_tickers_key(tmp_path: Path) -> None:
    p = tmp_path / "cohort.json"
    p.write_text(json.dumps({"tickers": ["aapl", "msft", "aapl", "", "NVDA"]}), encoding="utf-8")
    out = _cohort_symbols_from_file(p)
    assert out == ["AAPL", "MSFT", "NVDA"]


def test_cohort_file_reader_accepts_bare_list(tmp_path: Path) -> None:
    p = tmp_path / "cohort.json"
    p.write_text(json.dumps(["AAPL", "msft"]), encoding="utf-8")
    out = _cohort_symbols_from_file(p)
    assert out == ["AAPL", "MSFT"]
