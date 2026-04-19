"""Layer 1 Brain-bundle stale-asset adapter tests (AGH v1 B-patch).

The adapter must:

* Read the Brain bundle universe from JSON (read-only).
* Read ``raw_transcript_payloads_fmp`` + ``transcript_ingest_runs`` via a
  supplied Supabase client stub (read-only - never ``update``/``insert``).
* Emit candidates with ``expected_freshness_hours`` so Layer 1's scout can
  decide staleness deterministically.
* Honour env overrides for freshness hours.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_harness.adapters.layer1_brain_adapter import (
    DEFAULT_FRESHNESS_HOURS,
    _universe_from_brain_bundle,
    build_stale_asset_provider,
)
from agentic_harness.agents.layer1_ingest import source_scout_agent
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


# ---------------------------------------------------------------------------
# Brain bundle universe loader
# ---------------------------------------------------------------------------


def _write_brain_bundle(tmp_path, symbols: list[str]):
    buckets = {"short": [], "medium": [], "long": []}
    for i, s in enumerate(symbols):
        buckets[["short", "medium", "long"][i % 3]].append(
            {"asset_id": s, "horizon": "short", "residual_score": 0.1}
        )
    path = tmp_path / "metis_brain_bundle_v0_test.json"
    path.write_text(
        json.dumps(
            {
                "contract": "METIS_BRAIN_BUNDLE_V0",
                "spectrum_rows_by_horizon": buckets,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_universe_from_brain_bundle_returns_sorted_unique(monkeypatch, tmp_path):
    path = _write_brain_bundle(tmp_path, ["trgp", "BIIB", "TRGP", "amgn", "AMGN"])
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(path))
    out = _universe_from_brain_bundle()
    assert out == ["AMGN", "BIIB", "TRGP"]


def test_universe_from_missing_brain_bundle_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(tmp_path / "does_not_exist.json"))
    assert _universe_from_brain_bundle() == []


# ---------------------------------------------------------------------------
# StaleAssetProvider factory
# ---------------------------------------------------------------------------


class _FakeSupabaseClient:
    """Minimal read-only stub that records every table call.

    Raises if anyone tries to write; that way ``direct registry write = 0``
    is enforced by the test fixture itself.
    """

    def __init__(self, rows_by_symbol: dict[str, str]):
        self._rows_by_symbol = rows_by_symbol
        self.selects: list[tuple[str, tuple, dict]] = []

    def table(self, name: str) -> "_FakeTable":
        return _FakeTable(self, name)


class _FakeTable:
    def __init__(self, client: _FakeSupabaseClient, name: str):
        self._client = client
        self._name = name
        self._filters: dict[str, object] = {}
        self._select: str = ""
        self._order_col: str = ""
        self._order_desc: bool = False
        self._limit: int = 0

    def select(self, cols: str) -> "_FakeTable":
        self._select = cols
        return self

    def in_(self, col: str, values):
        self._filters[col] = ("in", list(values))
        return self

    def eq(self, col: str, value):
        self._filters[col] = ("eq", value)
        return self

    def filter(self, col: str, op: str, value):
        self._filters[col] = (op, value)
        return self

    def order(self, col: str, desc: bool = False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def insert(self, *_a, **_k):  # pragma: no cover
        raise AssertionError(f"adapter attempted a write to {self._name}")

    def update(self, *_a, **_k):  # pragma: no cover
        raise AssertionError(f"adapter attempted a write to {self._name}")

    def upsert(self, *_a, **_k):  # pragma: no cover
        raise AssertionError(f"adapter attempted a write to {self._name}")

    def delete(self, *_a, **_k):  # pragma: no cover
        raise AssertionError(f"adapter attempted a write to {self._name}")

    def execute(self):
        self._client.selects.append(
            (self._name, tuple(sorted(self._filters.items())), {"select": self._select})
        )
        data: list[dict] = []
        if self._name == "raw_transcript_payloads_fmp":
            op = self._filters.get("symbol")
            if op and op[0] == "in":
                for sym in op[1]:
                    ts = self._client._rows_by_symbol.get(sym)
                    if ts:
                        data.append({"symbol": sym, "fetched_at": ts})
        elif self._name == "transcript_ingest_runs":
            # fallback path - return empty so primary-only wins in this test
            data = []
        return _FakeResult(data)


class _FakeResult:
    def __init__(self, data):
        self.data = data


def test_build_stale_asset_provider_default_90d(monkeypatch, tmp_path):
    monkeypatch.delenv("METIS_HARNESS_L1_FRESHNESS_HOURS", raising=False)
    monkeypatch.delenv("METIS_HARNESS_L1_UNIVERSE_SOURCE", raising=False)
    path = _write_brain_bundle(tmp_path, ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"])
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(path))

    # Three symbols are "fresh" (fetched 10 days ago), four are stale (120 days
    # ago) / missing entirely.
    now = datetime.now(timezone.utc)
    fresh_ts = (now - timedelta(days=10)).isoformat()
    stale_ts = (now - timedelta(days=120)).isoformat()
    rows = {
        "AAA": fresh_ts,
        "BBB": fresh_ts,
        "CCC": fresh_ts,
        "DDD": stale_ts,
        "EEE": stale_ts,
        # FFF, GGG are missing entirely -> treated as stale
    }
    client = _FakeSupabaseClient(rows)
    provider = build_stale_asset_provider(client_factory=lambda: client)

    candidates = provider(FixtureHarnessStore(), now_utc_iso())
    by_id = {c["asset_id"]: c for c in candidates}
    assert set(by_id.keys()) == {"AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"}
    for c in candidates:
        assert c["expected_freshness_hours"] == DEFAULT_FRESHNESS_HOURS
        assert c["source_family"] == "earnings_transcript"
        assert any(r.startswith("brain_bundle://") for r in c["provenance_refs"])

    # source_scout_agent then filters to only the stale ones (>= 90d).
    stale = source_scout_agent(FixtureHarnessStore(), now_utc_iso())
    # scout uses the global provider, which isn't wired here; call with
    # provider directly by monkeypatching:
    from agentic_harness.agents import layer1_ingest as l1

    l1.set_stale_asset_provider(provider)
    try:
        stale = source_scout_agent(FixtureHarnessStore(), now_utc_iso())
    finally:
        l1.set_stale_asset_provider(None)
    stale_ids = sorted(s["asset_id"] for s in stale)
    assert stale_ids == ["DDD", "EEE", "FFF", "GGG"]


def test_build_stale_asset_provider_env_override_freshness(monkeypatch, tmp_path):
    path = _write_brain_bundle(tmp_path, ["AAA", "BBB"])
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(path))
    monkeypatch.setenv("METIS_HARNESS_L1_FRESHNESS_HOURS", "72")

    now = datetime.now(timezone.utc)
    # Both fetched 5 days ago -> stale at 72h threshold.
    rows = {
        "AAA": (now - timedelta(days=5)).isoformat(),
        "BBB": (now - timedelta(days=5)).isoformat(),
    }
    client = _FakeSupabaseClient(rows)
    provider = build_stale_asset_provider(client_factory=lambda: client)
    candidates = provider(FixtureHarnessStore(), now_utc_iso())
    assert all(c["expected_freshness_hours"] == 72 for c in candidates)

    from agentic_harness.agents import layer1_ingest as l1

    l1.set_stale_asset_provider(provider)
    try:
        stale = source_scout_agent(FixtureHarnessStore(), now_utc_iso())
    finally:
        l1.set_stale_asset_provider(None)
    assert sorted(s["asset_id"] for s in stale) == ["AAA", "BBB"]


def test_adapter_is_read_only_client(monkeypatch, tmp_path):
    path = _write_brain_bundle(tmp_path, ["AAA"])
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(path))

    client = _FakeSupabaseClient({"AAA": "2025-01-01T00:00:00+00:00"})
    provider = build_stale_asset_provider(client_factory=lambda: client)
    provider(FixtureHarnessStore(), now_utc_iso())

    # Every recorded call must target a read-safe table and must have issued
    # a select/in/eq/filter - never a write op (the fake would have raised).
    assert client.selects, "provider must have issued at least one read"
    for tbl, _, meta in client.selects:
        assert tbl in {"raw_transcript_payloads_fmp", "transcript_ingest_runs"}
        assert meta["select"]  # non-empty select list


def test_unknown_universe_source_raises(monkeypatch, tmp_path):
    path = _write_brain_bundle(tmp_path, ["AAA"])
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(path))
    with pytest.raises(ValueError):
        build_stale_asset_provider(
            client_factory=lambda: _FakeSupabaseClient({}),
            universe_source="watchlist",
        )
