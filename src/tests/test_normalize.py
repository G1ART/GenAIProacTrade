from __future__ import annotations

from datetime import datetime, timezone

from sec.normalize import (
    canonical_form_type,
    parse_accepted_at,
    parse_filed_at,
    raw_payload_to_normalized_summary,
)


def test_canonical_form_type() -> None:
    assert canonical_form_type("  10-q  ") == "10-Q"
    assert canonical_form_type("10-K / A") == "10-K/A"


def test_parse_filed_at() -> None:
    dt = parse_filed_at("2024-03-15")
    assert dt is not None
    assert dt.year == 2024 and dt.month == 3 and dt.day == 15
    assert dt.tzinfo == timezone.utc


def test_parse_accepted_at() -> None:
    dt = parse_accepted_at("2024-03-15T18:30:00+00:00")
    assert dt is not None
    naive = datetime(2024, 1, 1, 12, 0, 0)
    dt2 = parse_accepted_at(naive)
    assert dt2 is not None
    assert dt2.tzinfo == timezone.utc


def test_raw_payload_to_normalized_summary() -> None:
    payload = {
        "cik": "0000320193",
        "company_name": "Apple Inc.",
        "accession_no": "0000320193-24-000001",
        "form": "10-q",
        "filing_date": "2024-02-01",
        "acceptance_datetime": "2024-02-01T21:00:00+00:00",
    }
    s = raw_payload_to_normalized_summary(payload, revision_no=1)
    assert s["issuer"]["cik"] == "0000320193"
    assert s["filing"]["canonical_form"] == "10-Q"
    assert s["revision_no"] == 1
    assert s["timestamps"]["filed_at"] is not None
    assert s["timestamps"]["accepted_at"] is not None
