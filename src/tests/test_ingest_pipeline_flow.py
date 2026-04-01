from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sec.ingest_pipeline import ingest_filing_payload

PAYLOAD = {
    "source": "edgartools",
    "ticker_requested": "AAPL",
    "cik": "0000320193",
    "company_name": "Apple Inc.",
    "accession_no": "0000320193-24-000099",
    "form": "10-Q",
    "filing_date": "2024-06-01",
    "acceptance_datetime": "2024-06-01T20:00:00+00:00",
    "source_url": "https://example.com",
}


def test_ingest_filing_payload_calls_layers() -> None:
    client = MagicMock()
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    with (
        patch("sec.ingest_pipeline.upsert_issuer_master") as ui,
        patch("sec.ingest_pipeline.upsert_filing_index", return_value={"inserted": True, "updated": False}),
        patch("sec.ingest_pipeline.raw_filing_exists", return_value=False),
        patch("sec.ingest_pipeline.silver_filing_exists", return_value=False),
        patch("sec.ingest_pipeline.insert_raw_filing") as ir,
        patch("sec.ingest_pipeline.insert_silver_filing") as is_,
        patch("sec.ingest_pipeline.validate_filing_identity", return_value={"status": "skipped"}),
    ):
        out = ingest_filing_payload(client, PAYLOAD, company=None, now=now, run_validation_hook=True)
    ui.assert_called_once()
    ir.assert_called_once()
    is_.assert_called_once()
    assert out["raw_inserted"] is True
    assert out["silver_inserted"] is True
