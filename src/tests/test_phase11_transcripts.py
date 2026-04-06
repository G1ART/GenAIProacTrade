"""Phase 11: FMP transcript binding, normalization, overlay logic, scanner enrichment."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from main import build_parser
from sources import transcripts_provider_binding as bind
from sources.transcripts_normalizer import normalize_fmp_earning_call_payload
from scanner.transcript_enrichment import (
    build_transcript_enrichment_for_ticker,
    optional_why_matters_transcript_clause,
)


def test_phase11_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    for c in (
        "probe-transcripts-provider",
        "ingest-transcripts-sample",
        "report-transcripts-overlay-status",
        "export-transcript-normalization-sample",
    ):
        assert c in names


def test_classify_fmp_http_response() -> None:
    assert bind.classify_fmp_http_response(401, {}) == bind.FAILED_RIGHTS_OR_AUTH
    assert bind.classify_fmp_http_response(200, []) == bind.PARTIAL
    assert (
        bind.classify_fmp_http_response(
            200, [{"content": "hello", "date": "2020-07-30"}]
        )
        == bind.AVAILABLE
    )
    assert bind.classify_fmp_http_response(200, {"Error Message": "x"}) == bind.FAILED_RIGHTS_OR_AUTH


def test_overlay_availability_after_probe() -> None:
    assert bind.overlay_availability_after_probe(bind.AVAILABLE) == "available"
    assert bind.overlay_availability_after_probe(bind.PARTIAL) == "partial"
    assert bind.overlay_availability_after_probe(bind.FAILED_NETWORK) is None


def test_normalize_fmp_payload_ok() -> None:
    payload = [{"content": "Mgmt speaks.", "date": "2020-07-30 00:00:00"}]
    row = normalize_fmp_earning_call_payload(
        ticker="AAPL",
        fiscal_year=2020,
        fiscal_quarter=3,
        http_status=200,
        payload=payload,
        raw_payload_fmp_id="00000000-0000-0000-0000-000000000001",
        issuer_id=None,
    )
    assert row is not None
    assert row["normalization_status"] == "ok"
    assert row["source_rights_class"] == "premium"
    assert "pit_note" in row["provenance_json"]


@patch(
    "scanner.transcript_enrichment.dbrec.fetch_source_overlay_availability_by_key",
    return_value=None,
)
@patch(
    "scanner.transcript_enrichment.dbrec.fetch_normalized_transcripts_for_ticker_recent",
    return_value=[],
)
def test_transcript_enrichment_no_row(_mock_norm: object, _mock_ov: object) -> None:
    enr = build_transcript_enrichment_for_ticker(MagicMock(), ticker="ZZZZ")
    assert enr["normalized_transcript_row_present"] is False
    assert optional_why_matters_transcript_clause(enr) == ""


def test_pit_transcript_excludes_future_row() -> None:
    from scanner.transcript_enrichment import build_transcript_enrichment_for_candidate_context

    future_row = {
        "id": "f1",
        "normalization_status": "ok",
        "transcript_text": "hello",
        "available_at": "2025-06-01T00:00:00+00:00",
        "fiscal_period": "2025-Q2",
        "provenance_json": {},
    }
    past_row = {
        "id": "p1",
        "normalization_status": "ok",
        "transcript_text": "old",
        "available_at": "2020-01-01T00:00:00+00:00",
        "fiscal_period": "2019-Q4",
        "provenance_json": {},
    }
    client = MagicMock()

    def _recent(*_a, **_k):
        return [future_row, past_row]

    with patch(
        "scanner.transcript_enrichment.dbrec.fetch_normalized_transcripts_for_ticker_recent",
        side_effect=_recent,
    ), patch(
        "scanner.transcript_enrichment.dbrec.fetch_source_overlay_availability_by_key",
        return_value={"availability": "partial"},
    ):
        enr = build_transcript_enrichment_for_candidate_context(
            client, ticker="X", as_of_calendar_date="2020-03-15"
        )
    assert enr.get("normalized_transcript_id") == "p1"
    assert enr.get("pit_effective_date_used") == "2020-01-01"


def test_pit_transcript_no_anchor_excluded() -> None:
    from scanner.transcript_enrichment import build_transcript_enrichment_for_candidate_context

    no_dates = {
        "id": "n1",
        "normalization_status": "ok",
        "transcript_text": "x",
        "provenance_json": {},
    }
    client = MagicMock()
    with patch(
        "scanner.transcript_enrichment.dbrec.fetch_normalized_transcripts_for_ticker_recent",
        return_value=[no_dates],
    ), patch(
        "scanner.transcript_enrichment.dbrec.fetch_source_overlay_availability_by_key",
        return_value=None,
    ):
        enr = build_transcript_enrichment_for_candidate_context(
            client, ticker="X", as_of_calendar_date="2020-03-15"
        )
    assert enr["reason"] == "no_pit_safe_normalized_row"


def test_run_fmp_probe_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    from config import Settings

    s = Settings.model_validate(
        {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "EDGAR_IDENTITY": "test@test",
            "FMP_API_KEY": None,
            "TRANSCRIPTS_PROVIDER": "fmp",
        }
    )
    out = bind.run_fmp_probe(s)
    assert out["probe_status"] == bind.NOT_CONFIGURED


@patch("sources.transcripts_provider_binding.fetch_earning_call_transcript")
def test_run_fmp_probe_available(mock_fetch, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "k")
    from config import Settings

    s = Settings.model_validate(
        {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "EDGAR_IDENTITY": "a@b.c",
            "FMP_API_KEY": "k",
            "TRANSCRIPTS_PROVIDER": "fmp",
        }
    )
    mock_fetch.return_value = (
        200,
        [{"content": "x", "date": "2020-01-01"}],
    )
    out = bind.run_fmp_probe(s)
    assert out["probe_status"] == bind.AVAILABLE
