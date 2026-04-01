from __future__ import annotations

from unittest.mock import MagicMock

from db.records import (
    ingest_run_create_started,
    ingest_run_finalize,
    upsert_filing_index,
    upsert_issuer_master,
)


def test_upsert_issuer_master_insert_then_update() -> None:
    client = MagicMock()
    sel = (
        client.table.return_value.select.return_value.eq.return_value.limit.return_value
    )
    sel.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[{"id": "u1", "first_seen_at": "t0", "created_at": "t0"}]),
    ]
    now = "2026-01-01T00:00:00+00:00"
    row = {
        "cik": "0000320193",
        "ticker": "AAPL",
        "company_name": "Apple",
        "sic": None,
        "sic_description": None,
        "latest_known_exchange": None,
        "is_active": True,
        "first_seen_at": now,
        "last_seen_at": now,
        "created_at": now,
        "updated_at": now,
    }
    upsert_issuer_master(client, row)
    assert client.table.return_value.insert.called
    client.table.return_value.insert.reset_mock()
    client.table.return_value.update.reset_mock()
    sel.execute.side_effect = [
        MagicMock(data=[{"id": "u1", "first_seen_at": "t0", "created_at": "t0"}]),
    ]
    upsert_issuer_master(client, row)
    assert client.table.return_value.update.called


def test_upsert_filing_index_idempotent() -> None:
    client = MagicMock()
    sel = (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value
    )
    sel.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[{"id": "f1"}]),
    ]
    now = "2026-01-01T00:00:00+00:00"
    row = {
        "cik": "0000320193",
        "accession_no": "0000320193-24-000001",
        "form": "10-Q",
        "filed_at": now,
        "accepted_at": now,
        "source_url": None,
        "filing_primary_document": None,
        "filing_description": None,
        "is_amendment": False,
        "first_seen_at": now,
        "last_seen_at": now,
        "created_at": now,
        "updated_at": now,
    }
    r1 = upsert_filing_index(client, row)
    assert r1["inserted"] is True and r1["updated"] is False
    r2 = upsert_filing_index(client, row)
    assert r2["inserted"] is False and r2["updated"] is True


def test_ingest_run_lifecycle() -> None:
    client = MagicMock()
    ins = client.table.return_value.insert.return_value.execute
    ins.return_value = MagicMock(data=[{"id": "run-uuid-1"}])
    rid = ingest_run_create_started(
        client,
        run_type="sec_watchlist_metadata_ingest",
        target_count=3,
        metadata_json={"tickers": ["A"]},
    )
    assert rid == "run-uuid-1"
    ingest_run_finalize(
        client,
        run_id=rid,
        status="completed",
        success_count=2,
        failure_count=1,
        error_json={"errors": []},
    )
    assert client.table.call_count >= 2
