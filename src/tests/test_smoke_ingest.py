from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from config import load_settings
from models.raw_filing import RawSecFilingRow
from models.silver_filing import SilverSecFilingRow
from sec.ingest_company_sample import run_sample_ingest

SAMPLE_PAYLOAD = {
    "source": "edgartools",
    "ticker_requested": "AAPL",
    "cik": "0000320193",
    "company_name": "Apple Inc.",
    "accession_no": "0000320193-24-000099",
    "form": "10-Q",
    "filing_date": "2024-06-01",
    "acceptance_datetime": "2024-06-01T20:00:00+00:00",
    "source_url": "https://www.sec.gov/example-index.html",
}

_PIPE_OK = {
    "cik": SAMPLE_PAYLOAD["cik"],
    "accession_no": SAMPLE_PAYLOAD["accession_no"],
    "issuer_upserted": True,
    "filing_index_inserted": True,
    "filing_index_updated": False,
    "raw_inserted": True,
    "silver_inserted": True,
    "arelle_validation": {"status": "skipped"},
}

_PIPE_SKIP = {
    **_PIPE_OK,
    "raw_inserted": False,
    "silver_inserted": False,
    "filing_index_inserted": False,
    "filing_index_updated": True,
}


def test_raw_silver_row_supabase_shape() -> None:
    now = datetime.now(timezone.utc)
    raw = RawSecFilingRow(
        cik="0000320193",
        company_name="Apple Inc.",
        accession_no="0000320193-24-000099",
        form="10-Q",
        filed_at=now,
        accepted_at=now,
        source_url="https://example.com",
        payload_json=SAMPLE_PAYLOAD,
        ingested_at=now,
    )
    d = raw.to_supabase_dict()
    assert set(d.keys()) >= {
        "cik",
        "company_name",
        "accession_no",
        "form",
        "payload_json",
    }
    assert isinstance(d["payload_json"], dict)

    summary = {
        "issuer": {"cik": "0000320193", "company_name": "Apple Inc."},
        "filing": {"accession_no": "0000320193-24-000099", "canonical_form": "10-Q"},
        "timestamps": {},
        "revision_no": 1,
    }
    sil = SilverSecFilingRow(
        cik="0000320193",
        company_name="Apple Inc.",
        accession_no="0000320193-24-000099",
        form="10-Q",
        filed_at=now,
        accepted_at=now,
        normalized_summary_json=summary,
        revision_no=1,
        created_at=now,
    )
    sd = sil.to_supabase_dict()
    assert "normalized_summary_json" in sd
    assert sd["revision_no"] == 1


def test_run_sample_ingest_mocked_inserts() -> None:
    settings = load_settings()
    client = MagicMock()

    with patch("sec.ingest_company_sample.ingest_filing_payload", return_value=_PIPE_OK) as pipe:
        out = run_sample_ingest(
            "AAPL",
            settings,
            client=client,
            fetch_fn=lambda: dict(SAMPLE_PAYLOAD),
        )

    pipe.assert_called_once()
    assert out["raw_inserted"] is True
    assert out["silver_inserted"] is True
    assert out["accession_no"] == SAMPLE_PAYLOAD["accession_no"]


def test_run_sample_ingest_skips_when_exists() -> None:
    settings = load_settings()
    client = MagicMock()

    with patch("sec.ingest_company_sample.ingest_filing_payload", return_value=_PIPE_SKIP) as pipe:
        out = run_sample_ingest(
            "AAPL",
            settings,
            client=client,
            fetch_fn=lambda: dict(SAMPLE_PAYLOAD),
        )

    pipe.assert_called_once()
    assert out["raw_inserted"] is False
    assert out["silver_inserted"] is False
