from __future__ import annotations

from unittest.mock import MagicMock, patch

from config import load_settings
from sec.watchlist_ingest import run_watchlist_ingest


def test_run_watchlist_ingest_mocked() -> None:
    settings = load_settings()
    client = MagicMock()

    payloads_msft = [
        {
            "cik": "0000789019",
            "accession_no": "0000789019-24-000001",
            "company_name": "Microsoft",
            "form": "10-Q",
            "ticker_requested": "MSFT",
            "filing_date": "2024-01-01",
        }
    ]
    co = MagicMock()

    with (
        patch("sec.watchlist_ingest.load_watchlist", return_value=(["MSFT"], 1)),
        patch(
            "sec.watchlist_ingest.fetch_recent_filings_for_ticker",
            return_value=(payloads_msft, co),
        ),
        patch("sec.watchlist_ingest.ingest_filing_payload") as pipe,
        patch("sec.watchlist_ingest.ingest_run_create_started", return_value="r1"),
        patch("sec.watchlist_ingest.ingest_run_finalize") as fin,
        patch("sec.watchlist_ingest.time.sleep"),
    ):
        out = run_watchlist_ingest(settings, client=client, sleep_seconds=0)

    pipe.assert_called_once()
    assert out["run_id"] == "r1"
    assert out["success_count"] >= 1
    fin.assert_called_once()
