from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sec.facts.facts_pipeline import run_facts_extract_for_ticker


def _sample_extract_payload() -> dict:
    base = {
        "cik": "0000320193",
        "accession_no": "0000320193-26-000006",
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
        row("k-dei-fy", "dei:DocumentFiscalYearFocus", value_numeric=2026.0),
        row(
            "k-dei-fp",
            "dei:DocumentFiscalPeriodFocus",
            value_numeric=None,
            value_text="Q1",
        ),
        row(
            "k-ni",
            "us-gaap:NetIncomeLoss",
            value_numeric=42.0,
            period_start="2025-09-28",
            period_end="2025-12-27",
            instant_date=None,
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
    ]
    return {
        "ok": True,
        "ticker": "AAPL",
        "cik": "0000320193",
        "accession_no": "0000320193-26-000006",
        "form": "10-Q",
        "raw_rows": raw_rows,
        "filed_at": "2026-01-30T00:00:00+00:00",
        "accepted_at": None,
    }


@pytest.fixture
def patched_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sec.facts.facts_pipeline.extract_facts_for_ticker",
        lambda *a, **k: _sample_extract_payload(),
    )


def test_facts_pipeline_second_run_inserts_nothing(patched_extract, monkeypatch: pytest.MonkeyPatch) -> None:
    """동일 filing 재실행 시 raw/silver insert가 0건이어야 한다."""
    client = MagicMock()
    settings = MagicMock()
    settings.edgar_identity = "t t@t.com"

    raw_seen: set[str] = set()
    silver_seen: set[tuple[str, str, str]] = set()

    def raw_exists(_c, *, cik, accession_no, dedupe_key):
        k = f"{cik}|{accession_no}|{dedupe_key}"
        if k in raw_seen:
            return True
        raw_seen.add(k)
        return False

    def silver_exists(_c, *, cik, accession_no, canonical_concept, revision_no, fact_period_key):
        t = (cik, accession_no, canonical_concept, fact_period_key)
        if t in silver_seen:
            return True
        silver_seen.add(t)
        return False

    monkeypatch.setattr("db.records.raw_xbrl_fact_exists", raw_exists)
    monkeypatch.setattr("db.records.silver_xbrl_fact_exists", silver_exists)
    monkeypatch.setattr("db.records.insert_raw_xbrl_fact", MagicMock())
    monkeypatch.setattr("db.records.insert_silver_xbrl_fact", MagicMock())
    monkeypatch.setattr(
        "db.records.upsert_issuer_quarter_snapshot",
        MagicMock(return_value={"inserted": True, "updated": False}),
    )

    out1 = run_facts_extract_for_ticker(client, settings, "AAPL", run_validation_hook=False)
    out2 = run_facts_extract_for_ticker(client, settings, "AAPL", run_validation_hook=False)

    assert out1["ok"] and out2["ok"]
    assert out1["raw_inserted"] == 3
    assert out2["raw_inserted"] == 0
    assert out2["raw_skipped"] == 3
    assert out1["silver_inserted"] == 1
    assert out2["silver_inserted"] == 0
    assert out2["silver_skipped"] == 1
