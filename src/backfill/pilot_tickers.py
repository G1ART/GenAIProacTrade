"""고정 pilot 티커 세트 (config/backfill_pilot_tickers_v1.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT

_PILOT_PATH = PROJECT_ROOT / "config" / "backfill_pilot_tickers_v1.json"


def load_pilot_tickers_v1() -> list[str]:
    if not _PILOT_PATH.exists():
        return []
    raw: dict[str, Any] = json.loads(_PILOT_PATH.read_text(encoding="utf-8"))
    return [str(t).upper().strip() for t in raw.get("tickers", []) if str(t).strip()]


SMOKE_FALLBACK_TICKERS = ["NVDA", "MSFT", "AAPL", "JPM", "XOM"]
