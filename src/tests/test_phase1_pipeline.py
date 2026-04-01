from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from sec.ingest_pipeline import (
    filing_index_row_from_payload,
    is_amendment_form,
    issuer_row_from_payload_and_company,
)


def test_is_amendment_form() -> None:
    assert is_amendment_form("10-K/A") is True
    assert is_amendment_form("10-Q") is False


def test_filing_index_row_from_payload() -> None:
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    p = {
        "cik": "0000320193",
        "accession_no": "0000320193-24-000001",
        "form": "10-K/A",
        "filing_date": "2024-01-15",
        "acceptance_datetime": "2024-01-15T18:00:00+00:00",
        "source_url": "https://sec.gov/x",
        "primary_document": "a.htm",
        "primary_doc_description": "10-K",
    }
    row = filing_index_row_from_payload(p, now=now)
    assert row["cik"] == "0000320193"
    assert row["is_amendment"] is True
    assert row["filing_primary_document"] == "a.htm"


def test_issuer_row_from_payload_minimal() -> None:
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    p = {
        "cik": "0000320193",
        "ticker_requested": "AAPL",
        "company_name": "Apple Inc.",
    }
    row = issuer_row_from_payload_and_company(p, None, now=now)
    assert row["cik"] == "0000320193"
    assert row["ticker"] == "AAPL"


def test_arelle_validate_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sec.validation.arelle_check._check_arelle", lambda: False)
    from sec.validation.arelle_check import validate_filing_identity

    r = validate_filing_identity({"accession_no": "x"})
    assert r["status"] == "skipped"
    assert r["reason"] == "arelle_not_installed"
