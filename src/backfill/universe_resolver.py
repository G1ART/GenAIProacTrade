"""mode·universe·symbol_limit → 처리할 티커 목록 (결정적)."""

from __future__ import annotations

from typing import Any, Optional

from backfill.normalize import normalize_ticker_list
from backfill.pilot_tickers import SMOKE_FALLBACK_TICKERS, load_pilot_tickers_v1
from research.universe_slices import resolve_slice_symbols

BackfillMode = str  # smoke | pilot | full | extended


def resolve_backfill_tickers(
    client: Any,
    *,
    mode: BackfillMode,
    universe_name: str,
    symbol_limit: Optional[int] = None,
) -> tuple[list[str], dict[str, Any]]:
    """
    Returns (tickers, meta) — meta 에 requested/resolved/universe 설명.
    """
    u = universe_name.strip()
    base = resolve_slice_symbols(client, u)
    base_set = set(base)
    meta: dict[str, Any] = {
        "universe_name": u,
        "mode": mode,
        "universe_symbol_count": len(base),
    }

    if mode == "smoke":
        take = base[:5] if len(base) >= 5 else list(base)
        if len(take) < 3:
            take = [t for t in SMOKE_FALLBACK_TICKERS if t in base_set][:5]
        if len(take) < 3:
            take = SMOKE_FALLBACK_TICKERS[:5]
        tickers = normalize_ticker_list(take)
        meta["resolution_note"] = "smoke: universe[:5] 또는 fallback"
    elif mode == "pilot":
        pilot = load_pilot_tickers_v1()
        inter = [t for t in pilot if t in base_set]
        if not inter:
            cap = min(symbol_limit or 35, len(base))
            tickers = normalize_ticker_list(base[:cap])
            meta["resolution_note"] = "pilot: pilot JSON 과 universe 교집합 없음 → universe 앞쪽 cap"
        else:
            cap = symbol_limit or 50
            tickers = normalize_ticker_list(inter[:cap])
            meta["resolution_note"] = "pilot: backfill_pilot_tickers_v1 ∩ universe"
    elif mode in ("full", "extended"):
        cap = symbol_limit if symbol_limit is not None else len(base)
        tickers = normalize_ticker_list(base[: min(cap, len(base))])
        meta["resolution_note"] = f"{mode}: universe 앞쪽 cap={cap}"
    else:
        raise ValueError(f"unknown backfill mode: {mode!r}")

    meta["resolved_symbol_count"] = len(tickers)
    meta["requested_symbol_limit"] = symbol_limit
    return tickers, meta
