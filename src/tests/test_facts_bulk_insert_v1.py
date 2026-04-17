"""Bulk insert + paged existence fetch for raw/silver XBRL facts.

Backfill throughput regression guard (METIS_MVP Phase A2). The ingest pipeline
can no longer tolerate O(n) HTTP round-trips per fact row; these tests pin the
contract that `fetch_*_keys_for_filing` and `insert_*_bulk` operate in page +
chunk batches.
"""

from __future__ import annotations

from typing import Any

from db.records import (
    fetch_raw_xbrl_fact_dedupe_keys_for_filing,
    fetch_silver_xbrl_fact_keys_for_filing,
    insert_raw_xbrl_facts_bulk,
    insert_silver_xbrl_facts_bulk,
)


class _FakeSelect:
    """Mimics the chained postgrest query builder returning paged fixture data."""

    def __init__(self, outer: "_FakeTable") -> None:
        self._outer = outer
        self._fields: list[str] = []
        self._filters: dict[str, Any] = {}
        self._range: tuple[int, int] | None = None

    def eq(self, col: str, val: Any) -> "_FakeSelect":
        self._filters[col] = val
        return self

    def range(self, a: int, b: int) -> "_FakeSelect":
        self._range = (a, b)
        return self

    def execute(self) -> Any:
        rows = [r for r in self._outer.rows if all(r.get(k) == v for k, v in self._filters.items())]
        if self._range is not None:
            a, b = self._range
            rows = rows[a : b + 1]

        class _R:
            data = rows

        self._outer.calls.append({"op": "select", "filters": dict(self._filters), "range": self._range})
        return _R()


class _FakeInsert:
    def __init__(self, outer: "_FakeTable", payload: Any) -> None:
        self._outer = outer
        self._payload = payload

    def execute(self) -> Any:
        batch = self._payload if isinstance(self._payload, list) else [self._payload]
        self._outer.rows.extend(batch)
        self._outer.calls.append({"op": "insert", "n": len(batch)})

        class _R:
            data = batch

        return _R()


class _FakeTable:
    def __init__(self, name: str, rows: list[dict[str, Any]] | None = None) -> None:
        self.name = name
        self.rows: list[dict[str, Any]] = list(rows or [])
        self.calls: list[dict[str, Any]] = []

    def select(self, *_fields: str, **_kw: Any) -> _FakeSelect:
        return _FakeSelect(self)

    def insert(self, payload: Any) -> _FakeInsert:
        return _FakeInsert(self, payload)


class _FakeClient:
    def __init__(self, tables: dict[str, _FakeTable]) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeTable:
        return self._tables[name]


def test_fetch_raw_xbrl_fact_dedupe_keys_paginates_until_short_batch() -> None:
    existing_rows = [
        {"cik": "C1", "accession_no": "A1", "dedupe_key": f"k{i}"} for i in range(1500)
    ] + [
        {"cik": "C1", "accession_no": "OTHER", "dedupe_key": "k_other"},
        {"cik": "OTHER", "accession_no": "A1", "dedupe_key": "k_wrong_cik"},
    ]
    tbl = _FakeTable("raw_xbrl_facts", existing_rows)
    client = _FakeClient({"raw_xbrl_facts": tbl})
    keys = fetch_raw_xbrl_fact_dedupe_keys_for_filing(
        client, cik="C1", accession_no="A1", page_size=500
    )
    assert len(keys) == 1500
    assert "k_other" not in keys
    assert "k_wrong_cik" not in keys
    select_calls = [c for c in tbl.calls if c["op"] == "select"]
    assert [c["range"] for c in select_calls] == [(0, 499), (500, 999), (1000, 1499), (1500, 1999)]


def test_fetch_silver_xbrl_fact_keys_paginates_composite_tuple() -> None:
    rows = [
        {
            "cik": "C1",
            "accession_no": "A1",
            "canonical_concept": f"c{i % 3}",
            "revision_no": 1 if i % 2 == 0 else 2,
            "fact_period_key": f"p{i % 5}",
        }
        for i in range(1100)
    ]
    tbl = _FakeTable("silver_xbrl_facts", rows)
    client = _FakeClient({"silver_xbrl_facts": tbl})
    keys = fetch_silver_xbrl_fact_keys_for_filing(
        client, cik="C1", accession_no="A1", page_size=400
    )
    assert all(isinstance(k, tuple) and len(k) == 3 for k in keys)
    assert (str, int, str) == tuple(type(x) for x in next(iter(keys)))
    select_calls = [c for c in tbl.calls if c["op"] == "select"]
    assert [c["range"] for c in select_calls] == [(0, 399), (400, 799), (800, 1199)]


def test_insert_raw_xbrl_facts_bulk_chunks_by_size() -> None:
    tbl = _FakeTable("raw_xbrl_facts")
    client = _FakeClient({"raw_xbrl_facts": tbl})
    rows = [{"dedupe_key": f"k{i}"} for i in range(1250)]
    n = insert_raw_xbrl_facts_bulk(client, rows, chunk_size=500)
    assert n == 1250
    insert_calls = [c for c in tbl.calls if c["op"] == "insert"]
    assert [c["n"] for c in insert_calls] == [500, 500, 250]


def test_insert_silver_xbrl_facts_bulk_empty_is_noop() -> None:
    tbl = _FakeTable("silver_xbrl_facts")
    client = _FakeClient({"silver_xbrl_facts": tbl})
    n = insert_silver_xbrl_facts_bulk(client, [], chunk_size=500)
    assert n == 0
    assert [c for c in tbl.calls if c["op"] == "insert"] == []


def test_insert_bulk_custom_chunk_size_preserves_rows() -> None:
    tbl = _FakeTable("silver_xbrl_facts")
    client = _FakeClient({"silver_xbrl_facts": tbl})
    rows = [{"canonical_concept": f"c{i}"} for i in range(33)]
    n = insert_silver_xbrl_facts_bulk(client, rows, chunk_size=10)
    assert n == 33
    assert len(tbl.rows) == 33
    insert_calls = [c for c in tbl.calls if c["op"] == "insert"]
    assert [c["n"] for c in insert_calls] == [10, 10, 10, 3]
