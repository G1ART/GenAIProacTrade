"""run_facts_extract_for_ticker_multi: 복수 filing 백필 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sec.facts.facts_pipeline import run_facts_extract_for_ticker_multi


def _payload(accession: str, fiscal_year: int, fiscal_period: str) -> dict:
    base = {
        "cik": "0000320193",
        "accession_no": accession,
        "taxonomy": "us-gaap",
        "unit": "usd",
        "value_text": None,
        "filed_at": "2026-01-30T00:00:00+00:00",
        "accepted_at": None,
        "source_payload_json": {"period_type": "duration"},
    }

    def row(dedupe_key: str, concept: str, **extra):
        r = {**base, "dedupe_key": dedupe_key, "concept": concept}
        r.update(extra)
        return r

    raw_rows = [
        row(f"k-dei-fy-{accession}", "dei:DocumentFiscalYearFocus", value_numeric=fiscal_year),
        row(
            f"k-dei-fp-{accession}",
            "dei:DocumentFiscalPeriodFocus",
            value_numeric=None,
            value_text=fiscal_period,
        ),
        row(
            f"k-ni-{accession}",
            "us-gaap:NetIncomeLoss",
            value_numeric=42.0,
            period_start="2025-09-28",
            period_end="2025-12-27",
            instant_date=None,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        ),
    ]
    return {
        "ok": True,
        "ticker": "AAPL",
        "cik": "0000320193",
        "accession_no": accession,
        "form": "10-Q",
        "raw_fact_count": len(raw_rows),
        "raw_rows": raw_rows,
        "filed_at": "2026-01-30T00:00:00+00:00",
        "accepted_at": None,
    }


def _multi_payload(accessions_periods: list[tuple[str, int, str]]) -> dict:
    return {
        "ok": True,
        "ticker": "AAPL",
        "requested_limit": len(accessions_periods),
        "filings": [_payload(a, fy, fp) for a, fy, fp in accessions_periods],
    }


def test_run_facts_extract_for_ticker_multi_ingests_each_filing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """각 filing이 독립적으로 raw/silver/snapshot에 적재되어야 한다."""
    monkeypatch.setattr(
        "sec.facts.facts_pipeline.extract_facts_for_ticker_multi",
        lambda *a, **k: _multi_payload(
            [
                ("0000320193-26-000001", 2026, "Q1"),
                ("0000320193-25-000010", 2025, "Q4"),
                ("0000320193-25-000007", 2025, "Q3"),
            ]
        ),
    )

    raw_inserts: list[list[dict]] = []
    silver_inserts: list[list[dict]] = []

    def fetch_raw_keys(_c, *, cik, accession_no, **_k):
        return set()

    def fetch_silver_keys(_c, *, cik, accession_no, **_k):
        return set()

    def raw_bulk(_c, rows, **_k):
        raw_inserts.append(list(rows))
        return len(rows)

    def silver_bulk(_c, rows, **_k):
        silver_inserts.append(list(rows))
        return len(rows)

    upserts: list[dict] = []

    def upsert_snap(_c, row):
        upserts.append(row)
        return {"inserted": True, "updated": False}

    monkeypatch.setattr("db.records.fetch_raw_xbrl_fact_dedupe_keys_for_filing", fetch_raw_keys)
    monkeypatch.setattr("db.records.fetch_silver_xbrl_fact_keys_for_filing", fetch_silver_keys)
    monkeypatch.setattr("db.records.insert_raw_xbrl_facts_bulk", raw_bulk)
    monkeypatch.setattr("db.records.insert_silver_xbrl_facts_bulk", silver_bulk)
    monkeypatch.setattr("db.records.upsert_issuer_quarter_snapshot", upsert_snap)

    client = MagicMock()
    settings = MagicMock()
    settings.edgar_identity = "t t@t.com"

    out = run_facts_extract_for_ticker_multi(
        client, settings, "AAPL", limit=3, run_validation_hook=False
    )

    assert out["ok"]
    assert out["filings_ingested"] == 3
    assert out["filings_failed"] == 0
    assert out["raw_inserted_total"] == 9
    assert out["silver_inserted_total"] == 3
    assert len(upserts) == 3
    accessions = {r["accession_no"] for r in upserts}
    assert accessions == {
        "0000320193-26-000001",
        "0000320193-25-000010",
        "0000320193-25-000007",
    }


def test_run_facts_extract_for_ticker_multi_no_filings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """XBRL 공시가 없을 때 ok=False, errors 보존."""
    monkeypatch.setattr(
        "sec.facts.facts_pipeline.extract_facts_for_ticker_multi",
        lambda *a, **k: {
            "ok": False,
            "ticker": "AAPL",
            "requested_limit": 3,
            "filings": [],
            "error": "no_xbrl_filing",
            "forms": ["10-Q", "10-K"],
        },
    )

    client = MagicMock()
    settings = MagicMock()
    settings.edgar_identity = "t t@t.com"

    out = run_facts_extract_for_ticker_multi(
        client, settings, "AAPL", limit=3, run_validation_hook=False
    )

    assert out["ok"] is False
    assert out["filings_ingested"] == 0
    assert out["errors"]
    assert out["errors"][0].get("error") == "no_xbrl_filing"
