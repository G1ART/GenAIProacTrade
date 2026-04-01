from __future__ import annotations

from pathlib import Path

import pytest

from watchlist_config import default_watchlist_path, load_watchlist


def test_load_default_watchlist() -> None:
    tickers, n = load_watchlist(default_watchlist_path())
    assert "AAPL" in tickers
    assert n >= 1


def test_load_watchlist_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_watchlist(tmp_path / "nope.json")
