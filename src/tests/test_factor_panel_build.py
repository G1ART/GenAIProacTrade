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

    out = run_factor_panels_for_cik(
        MagicMock(), "0000320193", record_run=True, refresh_if_stale=False
    )
    assert inserted == []
    assert out["skipped_existing"] == 1
    assert out.get("refreshed_stale", 0) == 0


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

    run_factor_panels_for_cik(
        MagicMock(), "0000320193", record_run=True, refresh_if_stale=False
    )
    assert len(inserted) == 1
    assert inserted[0]["factor_version"] == DEFAULT_FACTOR_VERSION


def test_run_factor_panels_upserts_when_stale_nulls(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB에 NULL 패널이 있어도 스냅샷으로 값이 나오면 upsert."""
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
    snaps = [s1, s2]
    monkeypatch.setattr(
        "factors.panel_build.fetch_issuer_quarter_snapshots_for_cik",
        lambda _c, cik: snaps,
    )
    monkeypatch.setattr("factors.panel_build.factor_panel_exists", lambda *a, **k: True)
    inserted: list = []
    upserted: list = []
    monkeypatch.setattr(
        "factors.panel_build.insert_factor_panel", lambda _c, row: inserted.append(row)
    )
    monkeypatch.setattr(
        "factors.panel_build.upsert_factor_panel", lambda _c, row: upserted.append(row)
    )
    stale = {
        "accruals": None,
        "gross_profitability": None,
        "asset_growth": None,
        "capex_intensity": None,
        "rnd_intensity": None,
        "financial_strength_score": None,
    }
    monkeypatch.setattr(
        "factors.panel_build.fetch_factor_panel_by_identity",
        lambda *a, **k: dict(stale),
    )
    monkeypatch.setattr(
        "factors.panel_build.ingest_run_create_started", lambda *a, **k: "run1"
    )
    monkeypatch.setattr("factors.panel_build.ingest_run_finalize", MagicMock())

    out = run_factor_panels_for_cik(MagicMock(), "0000320193", record_run=True)
    assert inserted == []
    a2_rows = [u for u in upserted if u.get("accession_no") == "a2"]
    assert len(a2_rows) == 1
    assert a2_rows[0]["accruals"] is not None
    assert out["refreshed_stale"] >= 1


def test_ytd_subtraction_yields_qtd_for_accruals() -> None:
    """
    flow canonical이 YTD로 저장된 경우, 같은 FY의 직전 분기 YTD를 빼서
    QTD를 유도하는지 확인한다. AAPL/NVDA의 operating_cash_flow 시나리오 재현.
    """
    q1 = _snap(
        fy=2025,
        fp="Q1",
        acc="acc-q1",
        sid="00000000-0000-0000-0000-000000000q1",
        net_income=10.0,
        operating_cash_flow=12.0,  # YTD(3M) == QTD
        total_assets=100.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "ytd"},
            }
        },
    )
    q2 = _snap(
        fy=2025,
        fp="Q2",
        acc="acc-q2",
        sid="00000000-0000-0000-0000-000000000q2",
        net_income=22.0,  # 분기값 (quarterly)
        operating_cash_flow=30.0,  # YTD(6M) — Q2 QTD = 30-12 = 18
        total_assets=120.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "ytd"},
            }
        },
    )
    # Q1 prior (avg_total_assets 계산용으로 FY-1 Q4 필요)
    q4_prior = _snap(
        fy=2024,
        fp="Q4",
        acc="acc-q4-prior",
        sid="00000000-0000-0000-0000-000000000q4",
        total_assets=90.0,
    )

    row_q2 = build_factor_panel_row(q2, [q4_prior, q1, q2], factor_version="v1")

    # Q2 accruals = (NI - QTD_OCF) / avg_TA = (22 - (30-12)) / ((100+120)/2) = 4/110
    expected_accruals = (22.0 - (30.0 - 12.0)) / ((100.0 + 120.0) / 2.0)
    assert row_q2["accruals"] == pytest.approx(expected_accruals)

    adj = row_q2["coverage_json"]["period_basis_adjustments"]
    assert adj["operating_cash_flow"]["action"] == "ytd_minus_prior_ytd"
    assert adj["operating_cash_flow"]["qtd"] == pytest.approx(18.0)
    assert adj["operating_cash_flow"]["prior_accession_no"] == "acc-q1"
    # net_income은 이미 quarterly로 표기되어 변환 대상 아님
    assert "net_income" not in adj


def test_ytd_subtraction_uses_q1_quarterly_as_implicit_ytd() -> None:
    """
    Q1 snapshot의 flow canonical이 `basis="quarterly"` 로 저장돼 있어도
    실제로 3M YTD 와 동일하므로 Q2 의 subtraction chain 에서 유효한 prior-YTD 로
    취급되어야 한다 (AAPL/NVDA 2025 Q2 시나리오).
    """
    q4_prior_fy = _snap(
        fy=2024,
        fp="Q4",
        acc="acc-q4-prior",
        sid="00000000-0000-0000-0000-000000000q4",
        total_assets=90.0,
    )
    q1 = _snap(
        fy=2025,
        fp="Q1",
        acc="acc-q1",
        sid="00000000-0000-0000-0000-000000000q1",
        net_income=10.0,
        operating_cash_flow=12.0,  # 3M == YTD == QTD, but basis tagged quarterly
        total_assets=100.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "quarterly"},
            }
        },
    )
    q2 = _snap(
        fy=2025,
        fp="Q2",
        acc="acc-q2",
        sid="00000000-0000-0000-0000-000000000q2",
        net_income=22.0,
        operating_cash_flow=30.0,  # 6M YTD. Q2 QTD = 30 - 12 = 18
        total_assets=120.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "ytd"},
            }
        },
    )

    row_q2 = build_factor_panel_row(q2, [q4_prior_fy, q1, q2], factor_version="v1")
    adj = row_q2["coverage_json"]["period_basis_adjustments"]
    assert adj["operating_cash_flow"]["action"] == "ytd_minus_prior_ytd"
    assert adj["operating_cash_flow"]["qtd"] == pytest.approx(18.0)
    assert adj["operating_cash_flow"]["prior_fiscal_period"] == "Q1"

    expected_accruals = (22.0 - (30.0 - 12.0)) / ((100.0 + 120.0) / 2.0)
    assert row_q2["accruals"] == pytest.approx(expected_accruals)


def test_find_prior_snapshot_falls_back_from_q4_to_fy() -> None:
    """Q1 의 prior 가 `Q4` 스냅샷으로 존재하지 않으면 `FY` 스냅샷으로 fallback."""
    from factors.prior_period import find_prior_snapshot

    fy_prior = _snap(
        fy=2025,
        fp="FY",
        acc="acc-fy",
        sid="00000000-0000-0000-0000-0000000000fy",
        total_assets=200.0,
    )
    q1_current = _snap(
        fy=2026,
        fp="Q1",
        acc="acc-q1",
        sid="00000000-0000-0000-0000-000000000q1n",
        total_assets=220.0,
    )
    prior = find_prior_snapshot(q1_current, [fy_prior, q1_current])
    assert prior is not None
    assert prior["accession_no"] == "acc-fy"


def test_q1_accruals_computes_with_fy_fallback() -> None:
    """Q1 에 대해 10-K(FY) 만 있어도 average_total_assets 가 계산되어 accruals 가 나와야 한다."""
    fy_prior = _snap(
        fy=2025,
        fp="FY",
        acc="acc-fy",
        sid="00000000-0000-0000-0000-0000000000fy",
        total_assets=200.0,
    )
    q1 = _snap(
        fy=2026,
        fp="Q1",
        acc="acc-q1",
        sid="00000000-0000-0000-0000-000000000q1n",
        net_income=10.0,
        operating_cash_flow=8.0,
        total_assets=220.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "quarterly"},
            }
        },
    )
    row = build_factor_panel_row(q1, [fy_prior, q1], factor_version="v1")
    expected = (10.0 - 8.0) / ((200.0 + 220.0) / 2.0)
    assert row["accruals"] == pytest.approx(expected)
    assert row["coverage_json"]["prior_snapshot_found"] is True


def test_ytd_subtraction_skipped_when_prior_missing() -> None:
    """직전 분기 snapshot이 없으면 YTD→QTD 변환을 skip하고 partial_inputs로 남긴다."""
    q3 = _snap(
        fy=2025,
        fp="Q3",
        acc="acc-q3-only",
        sid="00000000-0000-0000-0000-000000000q3",
        net_income=23.0,
        operating_cash_flow=80.0,  # YTD(9M), prior Q2 없음 → skip
        total_assets=200.0,
        snapshot_json={
            "filled_canonicals": {
                "net_income": {"period_basis": "quarterly"},
                "operating_cash_flow": {"period_basis": "ytd"},
            }
        },
    )
    row = build_factor_panel_row(q3, [q3], factor_version="v1")
    adj = row["coverage_json"]["period_basis_adjustments"]
    assert adj["operating_cash_flow"]["action"] == "skipped"
    assert adj["operating_cash_flow"]["reason"] == "prior_same_fy_quarter_missing"
