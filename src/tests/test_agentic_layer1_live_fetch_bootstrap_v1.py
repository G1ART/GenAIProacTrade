"""Tests for the Layer 1 live-fetch bootstrap hook (AGH v1 Patch 1).

The hook should:

* Stay idle when the ``METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH`` env flag is
  OFF.
* Stay idle when the flag is ON but ``FMP_API_KEY`` is missing (fallback
  transcript fetcher remains in place and a warning is logged).
* Stay idle for fixture stores regardless of flag state.
* Replace ``_TRANSCRIPT_FETCHER`` when flag is ON + key is set + store is
  not a fixture store.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentic_harness import runtime as rt
from agentic_harness.agents import layer1_ingest
from agentic_harness.store import FixtureHarnessStore


class _DummyStore:
    """Placeholder non-fixture store sentinel."""


class _Settings:
    def __init__(self, key: str = "TEST_KEY") -> None:
        self.fmp_api_key = key
        self.transcripts_provider = "fmp"


@pytest.fixture(autouse=True)
def _reset_bootstrap(monkeypatch):
    rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED = False
    layer1_ingest.set_transcript_fetcher(None)
    yield
    rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED = False
    layer1_ingest.set_transcript_fetcher(None)


def _env_on(monkeypatch):
    monkeypatch.setenv("METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH", "1")


def _env_off(monkeypatch):
    monkeypatch.delenv("METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH", raising=False)


def test_bootstrap_noop_when_flag_off(monkeypatch):
    _env_off(monkeypatch)
    rt._maybe_bootstrap_layer1_live_fetch(_DummyStore(), use_fixture=False)
    assert layer1_ingest._TRANSCRIPT_FETCHER is None
    assert rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED is False


def test_bootstrap_noop_for_fixture_store(monkeypatch):
    _env_on(monkeypatch)
    rt._maybe_bootstrap_layer1_live_fetch(
        FixtureHarnessStore(), use_fixture=True
    )
    assert layer1_ingest._TRANSCRIPT_FETCHER is None
    assert rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED is False


def test_bootstrap_warns_and_skips_when_key_missing(monkeypatch, caplog):
    _env_on(monkeypatch)
    monkeypatch.setattr(
        "config.load_settings", lambda: _Settings(key=""), raising=True
    )
    with caplog.at_level("WARNING"):
        rt._maybe_bootstrap_layer1_live_fetch(_DummyStore(), use_fixture=False)
    assert layer1_ingest._TRANSCRIPT_FETCHER is None
    assert rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED is False
    assert any("FMP_API_KEY missing" in r.message for r in caplog.records)


def test_bootstrap_wires_transcript_fetcher_when_flag_and_key_present(
    monkeypatch,
):
    _env_on(monkeypatch)
    monkeypatch.setattr(
        "config.load_settings", lambda: _Settings(key="KEY"), raising=True
    )
    monkeypatch.setattr(
        "db.client.get_supabase_client", lambda settings: object(), raising=True
    )

    sentinel_fetcher = lambda job_meta: {"ok": True}

    def _fake_build(*, client_factory, settings):
        # build_transcript_fetcher should be called with the live factory
        # and real settings from load_settings.
        assert callable(client_factory)
        assert getattr(settings, "fmp_api_key", "") == "KEY"
        return sentinel_fetcher

    monkeypatch.setattr(
        "agentic_harness.adapters.layer1_transcript_fetcher.build_transcript_fetcher",
        _fake_build,
        raising=True,
    )

    rt._maybe_bootstrap_layer1_live_fetch(_DummyStore(), use_fixture=False)
    assert layer1_ingest._TRANSCRIPT_FETCHER is sentinel_fetcher
    assert rt._LAYER1_LIVE_FETCH_BOOTSTRAPPED is True

    # Idempotent: second call should not re-bootstrap.
    def _should_not_be_called(**_kwargs):
        raise AssertionError("build_transcript_fetcher called twice")

    monkeypatch.setattr(
        "agentic_harness.adapters.layer1_transcript_fetcher.build_transcript_fetcher",
        _should_not_be_called,
        raising=True,
    )
    rt._maybe_bootstrap_layer1_live_fetch(_DummyStore(), use_fixture=False)
    assert layer1_ingest._TRANSCRIPT_FETCHER is sentinel_fetcher
