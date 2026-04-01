from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from factors import DEFAULT_FACTOR_VERSION
from factors.compute_panel import build_factor_panel_row
from factors.panel_build import run_factor_panels_for_cik


def _snap(
    *,
    fy: int,
    fp: str,
    acc: str,
    sid: str = "00000000-0000-0000-0000-000000000001",
    **kwargs: float,
) -> dict:
    base = {
        "id": sid,
        "cik": "0000320193",
        "fiscal_year": fy,
        "fiscal_period": fp,
        "accession_no": acc,
        "revenue": None,
        "net_income": None,
        "operating_cash_flow": None,
        "total_assets": None,
        "total_liabilities": None,
        "gross_profit": None,
        "capex": None,
        "research_and_development": None,
        "snapshot_json": {},
    }
    base.update(kwargs)
    return base


def test_build_factor_panel_partial_coverage() -> None:
    s1 = _snap(fy=2025, fp="Q4", acc="a1", total_assets=100.0)
    s2 = _snap(
        fy=2026,
        fp="Q1",
        acc="a2",
        sid="00000000-0000-0000-0000-000000000002",
        net_income=10.0,
        operating_cash_flow=5.0,
        total_assets=200.0,
        gross_profit=50.0,
        revenue=100.0,
        research_and_development=10.0,
        capex=20.0,
        total_liabilities=80.0,
    )
    row = build_factor_panel_row(s2, [s1, s2], factor_version="v1")
    assert row["factor_version"] == "v1"
    assert row["accruals"] is not None
    assert row["coverage_json"]["prior_snapshot_found"] is True
    assert "quality_flags_json" in row


def test_run_factor_panels_skips_when_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    snaps = [
        _snap(fy=2026, fp="Q1", acc="x", net_income=1.0, operating_cash_flow=1.0, total_assets=10.0),
    ]
    monkeypatch.setattr(
        "factors.panel_build.fetch_issuer_quarter_snapshots_for_cik",
        lambda _c, cik: snaps,
    )
    monkeypatch.setattr("factors.panel_build.factor_panel_exists", lambda *a, **k: True)
    inserted: list = []
    monkeypatch.setattr(
        "factors.panel_build.insert_factor_panel", lambda _c, row: inserted.append(row)
    )
    monkeypatch.setattr(
        "factors.panel_build.ingest_run_create_started", lambda *a, **k: "run1"
    )
    monkeypatch.setattr("factors.panel_build.ingest_run_finalize", MagicMock())

    out = run_factor_panels_for_cik(MagicMock(), "0000320193", record_run=True)
    assert inserted == []
    assert out["skipped_existing"] == 1


def test_run_factor_panels_inserts_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    snaps = [
        _snap(
            fy=2026,
            fp="Q1",
            acc="x",
            net_income=1.0,
            operating_cash_flow=1.0,
            total_assets=10.0,
        ),
    ]
    monkeypatch.setattr(
        "factors.panel_build.fetch_issuer_quarter_snapshots_for_cik",
        lambda _c, cik: snaps,
    )
    monkeypatch.setattr("factors.panel_build.factor_panel_exists", lambda *a, **k: False)
    inserted: list = []
    monkeypatch.setattr(
        "factors.panel_build.insert_factor_panel", lambda _c, row: inserted.append(row)
    )
    monkeypatch.setattr(
        "factors.panel_build.ingest_run_create_started", lambda *a, **k: "run1"
    )
    monkeypatch.setattr("factors.panel_build.ingest_run_finalize", MagicMock())

    run_factor_panels_for_cik(MagicMock(), "0000320193", record_run=True)
    assert len(inserted) == 1
    assert inserted[0]["factor_version"] == DEFAULT_FACTOR_VERSION
