"""Financial Modeling Prep — earning_call_transcript v3 (single Phase 11 binding)."""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FMP_V3_BASE = "https://financialmodelingprep.com/api/v3"


def fetch_earning_call_transcript(
    api_key: str,
    *,
    symbol: str,
    year: int,
    quarter: int,
    timeout_sec: float = 45.0,
) -> Tuple[int, Any]:
    """
    Returns (http_status, parsed_json).
    On network/parse failure raises; caller maps to probe/ingest status.
    """
    sym = symbol.strip().upper()
    q = urlencode(
        {"year": int(year), "quarter": int(quarter), "apikey": api_key.strip()}
    )
    url = f"{FMP_V3_BASE}/earning_call_transcript/{sym}?{q}"
    req = Request(url, headers={"User-Agent": "GenAIProacTrade/phase11-transcript-poc"})
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200) or 200
    except HTTPError as e:
        return int(e.code), _try_json(e.read().decode("utf-8", errors="replace"))
    except URLError as e:
        raise RuntimeError(f"fmp_network_error:{e}") from e

    try:
        parsed: Any = json.loads(body)
    except json.JSONDecodeError:
        return status, {"_parse_error": True, "raw_prefix": body[:500]}
    return status, parsed


def _try_json(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {"_non_json_error_body": s[:800]}
