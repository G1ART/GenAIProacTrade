"""`fetch_tickers_for_ciks` 배치 조회·norm 키·청크."""

from __future__ import annotations

from unittest.mock import MagicMock

from db.records import fetch_tickers_for_ciks
from research_validation.metrics import norm_cik


def test_fetch_tickers_for_ciks_empty() -> None:
    client = MagicMock()
    assert fetch_tickers_for_ciks(client, []) == {}


def test_fetch_tickers_for_ciks_norm_key_and_sorted_tiebreak() -> None:
    client = MagicMock()
    t = client.table.return_value
    t.select.return_value = t
    t.in_.return_value = t
    t.execute.return_value = MagicMock(
        data=[
            {"cik": "0000320193", "ticker": "ZZZ"},
            {"cik": "0000320193", "ticker": "AAA"},
        ]
    )
    out = fetch_tickers_for_ciks(client, ["0000320193"])
    nk = norm_cik("0000320193")
    assert nk in out
    assert out[nk] == "AAA"


def test_fetch_tickers_for_ciks_chunks_in_queries() -> None:
    client = MagicMock()
    t = client.table.return_value
    t.select.return_value = t
    t.in_.return_value = t
    raw = [f"c{i}" for i in range(85)]
    in_sizes: list[int] = []

    def _exec() -> MagicMock:
        return MagicMock(data=[])

    t.in_.side_effect = lambda _col, vals: in_sizes.append(len(list(vals))) or t
    t.execute.side_effect = _exec
    fetch_tickers_for_ciks(client, raw)
    assert in_sizes == [80, 5]
