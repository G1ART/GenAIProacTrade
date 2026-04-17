"""
Select ~200 backfill tickers from Supabase universes with deterministic sector diversity.

Sources:
  * ``universe_memberships`` — latest ``sp500_current`` + ``sp500_proxy_candidates_v1``
  * ``market_metadata_latest`` — per-symbol ``market_cap`` and ``sector``

Selection order (deterministic given DB snapshot):
  1. Mag 7 (AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA) — unconditional if resolvable.
  2. Remaining slots by ``market_cap`` desc with per-sector cap ~25% (default 50).
  3. Fill residual slots by raw market_cap desc when cap reached (diversity cap is soft).

Writes ``data/mvp/backfill_200_v1.json`` with per-ticker rationale for audit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from config import load_settings  # noqa: E402
from db.client import get_supabase_client  # noqa: E402
from db.records import fetch_market_metadata_latest_rows_for_symbols  # noqa: E402
from research.universe_slices import (  # noqa: E402
    UNIVERSE_PROXY_CANDIDATES,
    UNIVERSE_SP500_CURRENT,
    _latest_symbols_for_universe,
)

TARGET_N = 200
SECTOR_CAP_RATIO = 0.25
MAG7 = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]
UNKNOWN_SECTOR = "_unknown"


def _fetch_cik_map_for_symbols(client: Any, symbols: list[str]) -> dict[str, str]:
    """symbol -> cik from issuer_master (chunked)."""
    out: dict[str, str] = {}
    uniq: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        u = str(s).upper().strip()
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    step = 120
    for i in range(0, len(uniq), step):
        part = uniq[i : i + step]
        r = (
            client.table("issuer_master")
            .select("ticker,cik")
            .in_("ticker", part)
            .execute()
        )
        for row in r.data or []:
            t = str(row.get("ticker") or "").upper().strip()
            c = str(row.get("cik") or "").strip()
            if t and c and t not in out:
                out[t] = c
    return out


def _symbol_pool(client: Any) -> list[str]:
    a = set(_latest_symbols_for_universe(client, UNIVERSE_SP500_CURRENT))
    b = set(_latest_symbols_for_universe(client, UNIVERSE_PROXY_CANDIDATES))
    return sorted(a | b)


def select_backfill_200(client: Any) -> dict[str, Any]:
    pool = _symbol_pool(client)
    meta_by_sym = fetch_market_metadata_latest_rows_for_symbols(client, pool)
    cik_by_sym = _fetch_cik_map_for_symbols(client, pool)

    def score(sym: str) -> tuple[float, str]:
        m = meta_by_sym.get(sym) or {}
        mc = m.get("market_cap")
        mc_v = float(mc) if mc is not None else -1.0
        return (mc_v, sym)

    sector_cap = max(1, int(TARGET_N * SECTOR_CAP_RATIO))
    selected: dict[str, dict[str, Any]] = {}
    sector_counts: dict[str, int] = {}

    def add(sym: str, rationale: str) -> None:
        if sym in selected:
            return
        m = meta_by_sym.get(sym) or {}
        sector = str(m.get("sector") or UNKNOWN_SECTOR).strip() or UNKNOWN_SECTOR
        selected[sym] = {
            "ticker": sym,
            "cik": cik_by_sym.get(sym),
            "sector": sector,
            "market_cap": m.get("market_cap"),
            "rationale": rationale,
            "selection_rank": len(selected) + 1,
        }
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    for sym in MAG7:
        if sym in cik_by_sym:
            add(sym, "mag7_unconditional")

    pool_sorted = sorted(pool, key=score, reverse=True)

    for sym in pool_sorted:
        if len(selected) >= TARGET_N:
            break
        if sym in selected:
            continue
        if sym not in cik_by_sym:
            continue
        m = meta_by_sym.get(sym) or {}
        if m.get("market_cap") is None:
            continue
        sector = str(m.get("sector") or UNKNOWN_SECTOR).strip() or UNKNOWN_SECTOR
        if sector_counts.get(sector, 0) >= sector_cap and sector != UNKNOWN_SECTOR:
            continue
        add(sym, f"sector_diverse_topcap:{sector}")

    if len(selected) < TARGET_N:
        for sym in pool_sorted:
            if len(selected) >= TARGET_N:
                break
            if sym in selected or sym not in cik_by_sym:
                continue
            m = meta_by_sym.get(sym) or {}
            if m.get("market_cap") is None:
                continue
            add(sym, "residual_topcap_fill")

    if len(selected) < TARGET_N:
        for sym in pool_sorted:
            if len(selected) >= TARGET_N:
                break
            if sym in selected or sym not in cik_by_sym:
                continue
            add(sym, "sp500_plus_proxy_pool_no_metadata")

    ordered = sorted(selected.values(), key=lambda r: r["selection_rank"])
    return {
        "contract": "BACKFILL_200_V1",
        "target_n": TARGET_N,
        "actual_n": len(ordered),
        "sector_cap": sector_cap,
        "mag7": MAG7,
        "pool_universes": [UNIVERSE_SP500_CURRENT, UNIVERSE_PROXY_CANDIDATES],
        "pool_size": len(pool),
        "with_market_cap_in_pool": sum(
            1 for s in pool if (meta_by_sym.get(s) or {}).get("market_cap") is not None
        ),
        "sector_counts": dict(sorted(sector_counts.items(), key=lambda kv: -kv[1])),
        "tickers": [r["ticker"] for r in ordered],
        "rows": ordered,
    }


def main() -> int:
    settings = load_settings()
    client = get_supabase_client(settings)
    out = select_backfill_200(client)

    out_path = REPO_ROOT / "data" / "mvp" / "backfill_200_v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_path": str(out_path.relative_to(REPO_ROOT)),
                "target_n": out["target_n"],
                "actual_n": out["actual_n"],
                "pool_size": out["pool_size"],
                "with_market_cap_in_pool": out["with_market_cap_in_pool"],
                "sector_counts": out["sector_counts"],
                "first_10": out["tickers"][:10],
                "last_5": out["tickers"][-5:],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
