"""워치리스트 JSON 로드 (티커 목록 + issuer당 수집 공시 건수)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Tuple

from config import PROJECT_ROOT


def default_watchlist_path() -> Path:
    return PROJECT_ROOT / "config" / "watchlist.json"


def load_watchlist(path: Path | None = None) -> Tuple[List[str], int]:
    """
    Returns:
        (uppercase tickers, filings_per_issuer)
    """
    p = path or default_watchlist_path()
    if not p.exists():
        raise FileNotFoundError(f"워치리스트 파일이 없습니다: {p}")
    raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    tickers = [str(t).upper().strip() for t in raw.get("tickers", []) if str(t).strip()]
    if not tickers:
        raise ValueError("watchlist.json 에 유효한 tickers 가 없습니다.")
    n = int(raw.get("filings_per_issuer", 1))
    if n < 1:
        raise ValueError("filings_per_issuer 는 1 이상이어야 합니다.")
    return tickers, n
