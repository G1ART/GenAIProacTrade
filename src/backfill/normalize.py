"""CIK·티커 정규화 (결정적)."""

from __future__ import annotations


def normalize_ticker(sym: str) -> str:
    return str(sym or "").upper().strip()


def pad_cik_10(cik: str) -> str:
    d = "".join(c for c in str(cik or "") if c.isdigit())
    if not d:
        return ""
    return d.zfill(10)[-10:]


def normalize_ticker_list(tickers: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        u = normalize_ticker(t)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out
