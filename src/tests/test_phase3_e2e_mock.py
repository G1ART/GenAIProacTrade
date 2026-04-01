from __future__ import annotations

from factors.compute_panel import build_factor_panel_row, sort_snapshots_accounting_order


def test_sort_snapshots_accounting_order() -> None:
    rows = [
        {"fiscal_year": 2026, "fiscal_period": "Q2", "cik": "1", "accession_no": "b"},
        {"fiscal_year": 2026, "fiscal_period": "Q1", "cik": "1", "accession_no": "a"},
    ]
    s = sort_snapshots_accounting_order(rows)
    assert s[0]["accession_no"] == "a"


def test_snapshot_to_panel_end_to_end_minimal() -> None:
    """extract된 스냅샷 형태 → 패널 행 (prior 없음, 다수 팩터 null 허용)."""
    s = {
        "id": "11111111-1111-1111-1111-111111111111",
        "cik": "0000789019",
        "fiscal_year": 2026,
        "fiscal_period": "Q1",
        "accession_no": "0000789019-26-000001",
        "net_income": 5.0,
        "operating_cash_flow": 3.0,
        "total_assets": 100.0,
        "revenue": None,
        "gross_profit": None,
        "capex": None,
        "research_and_development": None,
        "total_liabilities": None,
        "snapshot_json": {},
    }
    row = build_factor_panel_row(s, [s], factor_version="v1")
    assert row["cik"] == "0000789019"
    assert row["snapshot_id"] == "11111111-1111-1111-1111-111111111111"
    assert row["coverage_json"]["prior_snapshot_found"] is False
