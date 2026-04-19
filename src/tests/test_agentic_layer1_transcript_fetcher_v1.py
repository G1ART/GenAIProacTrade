"""Tests for the Layer 1 live FMP transcript fetcher adapter (AGH v1 Patch 1).

Covers:

* fiscal-quarter inference table (12 months)
* ``classify_fmp_result`` branches (ok / empty / 404 / 401-403 / 429 / 5xx / unexpected)
* ``build_transcript_fetcher`` contract output including provenance refs
* RuntimeError handling (network error = retryable, api key missing = fail-fast)
* No Supabase / registry side effects outside the injected
  ``run_fmp_sample_ingest`` function.

All tests mock ``run_fmp_sample_ingest`` so there is zero network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest

from agentic_harness.adapters.layer1_transcript_fetcher import (
    FetchClassification,
    _infer_target_fiscal_quarter,
    _parse_fiscal_target_override,
    build_transcript_fetcher,
    classify_fmp_result,
)
from sources import transcripts_provider_binding as bind


# ---------------------------------------------------------------------------
# Fiscal-quarter inference
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "month, expected",
    [
        (1, (2025, 4)),
        (2, (2025, 4)),
        (3, (2025, 4)),
        (4, (2026, 1)),
        (5, (2026, 1)),
        (6, (2026, 1)),
        (7, (2026, 2)),
        (8, (2026, 2)),
        (9, (2026, 2)),
        (10, (2026, 3)),
        (11, (2026, 3)),
        (12, (2026, 3)),
    ],
)
def test_infer_target_fiscal_quarter_covers_all_months(month: int, expected):
    now = datetime(2026, month, 15, 12, 0, tzinfo=timezone.utc)
    assert _infer_target_fiscal_quarter(now) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", None),
        ("   ", None),
        ("2025-Q2", (2025, 2)),
        ("2025-q4", (2025, 4)),
        ("2025-Q5", None),
        ("abc-Q1", None),
        ("2025", None),
    ],
)
def test_parse_fiscal_target_override(raw: str, expected):
    assert _parse_fiscal_target_override(raw) == expected


# ---------------------------------------------------------------------------
# classify_fmp_result
# ---------------------------------------------------------------------------


def test_classify_200_available_ok():
    r = classify_fmp_result(200, bind.AVAILABLE, payload=[{"content": "hi"}])
    assert r == FetchClassification(ok=True, fetch_outcome="ok", retryable=False)


def test_classify_200_partial_empty_is_honest_empty():
    r = classify_fmp_result(200, bind.PARTIAL, payload=[])
    assert r.ok is True
    assert r.fetch_outcome == "empty"
    assert r.retryable is False
    assert "transcript_payload_empty_list" in r.blocking_reasons


def test_classify_200_with_error_body_is_auth_failfast():
    r = classify_fmp_result(200, bind.FAILED_RIGHTS_OR_AUTH, payload=None)
    assert r.ok is False
    assert r.retryable is False
    assert r.error.startswith("fmp_auth_failed")


def test_classify_200_unverified_shape_is_honest_empty():
    r = classify_fmp_result(200, bind.CONFIGURED_BUT_UNVERIFIED, payload=None)
    assert r.ok is True
    assert r.fetch_outcome == "empty"
    assert "transcript_payload_unexpected_shape" in r.blocking_reasons


def test_classify_404_is_honest_empty_not_retryable():
    r = classify_fmp_result(404, bind.PARTIAL, payload=None)
    assert r.ok is True
    assert r.fetch_outcome == "empty"
    assert r.retryable is False
    assert "transcript_not_available_for_quarter" in r.blocking_reasons


@pytest.mark.parametrize("code", [401, 402, 403])
def test_classify_auth_codes_fail_fast(code: int):
    r = classify_fmp_result(code, bind.FAILED_RIGHTS_OR_AUTH, payload=None)
    assert r.ok is False
    assert r.retryable is False
    assert r.error == f"fmp_auth_failed:{code}"


def test_classify_429_is_retryable():
    r = classify_fmp_result(429, bind.FAILED_RIGHTS_OR_AUTH, payload=None)
    assert r.ok is False
    assert r.retryable is True
    assert r.error.startswith("fmp_rate_limited")


@pytest.mark.parametrize("code", [500, 502, 503, 599])
def test_classify_5xx_is_retryable(code: int):
    r = classify_fmp_result(code, bind.FAILED_RIGHTS_OR_AUTH, payload=None)
    assert r.ok is False
    assert r.retryable is True
    assert r.error.startswith("fmp_server_error:")


def test_classify_other_status_is_retryable_defensive():
    r = classify_fmp_result(418, "", payload=None)
    assert r.ok is False
    assert r.retryable is True
    assert r.error.startswith("fmp_unexpected_http:")


# ---------------------------------------------------------------------------
# build_transcript_fetcher
# ---------------------------------------------------------------------------


@dataclass
class _Settings:
    fmp_api_key: str = "TEST_KEY"
    transcripts_provider: str = "fmp"


class _SentinelClient:
    """Distinct marker so tests can assert the factory was called exactly
    once and its result was not leaked outside the fetcher."""


def _frozen_now(year: int = 2026, month: int = 5, day: int = 15) -> datetime:
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


def test_build_fetcher_success_returns_ok_with_provenance():
    calls: list[Any] = []

    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        calls.append(
            {
                "client": client,
                "symbol": symbol,
                "year": year,
                "quarter": quarter,
                "op": operational_run_id,
            }
        )
        return {
            "symbol": symbol,
            "year": year,
            "quarter": quarter,
            "http_status": 200,
            "classify": bind.AVAILABLE,
            "transcript_ingest_run_id": "run-1",
            "raw_payload_fmp_id": "raw-1",
            "normalized_transcript_id": "norm-1",
            "normalization_status": "ok",
            "overlay_availability": "available",
        }

    sentinel = _SentinelClient()
    factory_calls = {"n": 0}

    def factory():
        factory_calls["n"] += 1
        return sentinel

    fetcher = build_transcript_fetcher(
        client_factory=factory,
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher(
        {
            "asset_id": "AAPL",
            "source_family": "earnings_transcript",
            "alert_packet_id": "pkt_smoke",
        }
    )

    assert res["ok"] is True
    assert res["fetch_outcome"] == "ok"
    assert res["artifact_kind"] == "transcript_text"
    assert res["artifact_ref"] == "raw-1"
    assert res["http_status"] == 200
    assert res["probe_status"] == bind.AVAILABLE
    assert res["confidence"] == pytest.approx(0.9)
    provs = list(res["provenance_refs"])
    assert "supabase://transcript_ingest_runs/run-1" in provs
    assert "supabase://raw_transcript_payloads_fmp/raw-1" in provs
    assert any(p.startswith("fmp://earning_call_transcript/AAPL/") for p in provs)
    assert "packet:pkt_smoke" in provs
    assert factory_calls["n"] == 1
    assert calls[0]["symbol"] == "AAPL"
    # inferred target for May -> Q1 of current year
    assert calls[0]["year"] == 2026
    assert calls[0]["quarter"] == 1


def test_build_fetcher_404_reports_empty_with_blocking_reasons():
    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        return {
            "http_status": 404,
            "classify": bind.PARTIAL,
            "transcript_ingest_run_id": "run-404",
            "raw_payload_fmp_id": "",
            "normalization_status": "none",
            "overlay_availability": "not_available_yet",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "DEMO_KR_A", "alert_packet_id": "pkt_demo"})
    assert res["ok"] is True
    assert res["fetch_outcome"] == "empty"
    assert res["http_status"] == 404
    assert res["confidence"] == pytest.approx(0.5)
    assert "transcript_not_available_for_quarter" in res["blocking_reasons"]


@pytest.mark.parametrize("code, err_prefix", [(401, "fmp_auth_failed:"), (403, "fmp_auth_failed:")])
def test_build_fetcher_auth_failfast(code: int, err_prefix: str):
    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        return {
            "http_status": code,
            "classify": bind.FAILED_RIGHTS_OR_AUTH,
            "transcript_ingest_run_id": "run-auth",
            "raw_payload_fmp_id": "",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is False
    assert res["error"].startswith(err_prefix)
    assert res["http_status"] == code


def test_build_fetcher_429_is_retryable():
    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        return {
            "http_status": 429,
            "classify": bind.FAILED_RIGHTS_OR_AUTH,
            "transcript_ingest_run_id": "run-429",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is True
    assert res["error"].startswith("fmp_rate_limited")


def test_build_fetcher_5xx_is_retryable():
    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        return {
            "http_status": 503,
            "classify": bind.FAILED_RIGHTS_OR_AUTH,
            "transcript_ingest_run_id": "run-503",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is True
    assert res["error"].startswith("fmp_server_error:")


def test_build_fetcher_network_runtime_error_is_retryable():
    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        raise RuntimeError("fmp_network_error: timed out")

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is True
    assert res["error"] == "fmp_network_error"


def test_build_fetcher_missing_api_key_failfast():
    called = {"n": 0}

    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        called["n"] += 1
        return {}

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(fmp_api_key=""),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is False
    assert res["error"] == "fmp_api_key_missing"
    assert called["n"] == 0


def test_build_fetcher_force_target_override(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        captured["year"] = year
        captured["quarter"] = quarter
        return {
            "http_status": 200,
            "classify": bind.AVAILABLE,
            "transcript_ingest_run_id": "run",
            "raw_payload_fmp_id": "raw",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher(
        {
            "asset_id": "AAPL",
            "alert_packet_id": "pkt",
            "_force_target": {"year": 2025, "quarter": 2},
        }
    )
    assert res["ok"] is True
    assert captured == {"year": 2025, "quarter": 2}


def test_build_fetcher_env_fiscal_override(monkeypatch):
    monkeypatch.setenv("METIS_HARNESS_L1_FISCAL_TARGET", "2024-Q3")
    captured: dict[str, Any] = {}

    def fake_ingest(client, settings, *, symbol, year, quarter, operational_run_id=None):
        captured["year"] = year
        captured["quarter"] = quarter
        return {
            "http_status": 200,
            "classify": bind.AVAILABLE,
            "transcript_ingest_run_id": "r",
            "raw_payload_fmp_id": "p",
        }

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    fetcher({"asset_id": "AAPL", "alert_packet_id": "pkt"})
    assert captured == {"year": 2024, "quarter": 3}


def test_build_fetcher_missing_asset_id_failfast():
    called = {"n": 0}

    def fake_ingest(*a, **kw):
        called["n"] += 1
        return {}

    fetcher = build_transcript_fetcher(
        client_factory=lambda: _SentinelClient(),
        settings=_Settings(),
        now_fn=_frozen_now,
        run_fmp_sample_ingest_fn=fake_ingest,
    )
    res = fetcher({"asset_id": "", "alert_packet_id": "pkt"})
    assert res["ok"] is False
    assert res["retryable"] is False
    assert res["error"] == "fetcher_missing_asset_id"
    assert called["n"] == 0
