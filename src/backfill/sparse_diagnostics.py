"""Sparse issuer / 단계별 조인 누락 진단 (수동 INSERT 없이 조회만)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backfill.checkpoint_report import _paginate_table


def _cik_ticker_map(client: Any) -> dict[str, str]:
    m: dict[str, str] = {}
    for row in _paginate_table(client, "issuer_master", "cik,ticker", 2000):
        ck = str(row.get("cik") or "").strip()
        if not ck:
            continue
        t = str(row.get("ticker") or "").upper().strip()
        m[ck] = t or ck
    return m


def _distinct_cik_set(client: Any, table: str) -> set[str]:
    s: set[str] = set()
    for row in _paginate_table(client, table, "cik", 2000):
        ck = str(row.get("cik") or "").strip()
        if ck:
            s.add(ck)
    return s


def _counts_per_cik(client: Any, table: str) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for row in _paginate_table(client, table, "cik", 2000):
        ck = str(row.get("cik") or "").strip()
        if ck:
            c[ck] += 1
    return dict(c)


def build_sparse_issuer_diagnostics(
    client: Any,
    *,
    max_list: int = 200,
) -> dict[str, Any]:
    """
    issuer_master → filing → silver → snapshot → factor → validation → score
    체인별 누락 및 저분기·저팩터행 issuer.
    """
    ticker_by_cik = _cik_ticker_map(client)
    master_ciks = set(ticker_by_cik.keys())
    filing_ciks = _distinct_cik_set(client, "filing_index")
    silver_ciks = _distinct_cik_set(client, "silver_xbrl_facts")
    snap_ciks = _distinct_cik_set(client, "issuer_quarter_snapshots")
    factor_ciks = _distinct_cik_set(client, "issuer_quarter_factor_panels")
    val_ciks = _distinct_cik_set(client, "factor_market_validation_panels")
    score_ciks = _distinct_cik_set(client, "issuer_state_change_scores")

    def _rows(name: str, ciks: set[str]) -> dict[str, Any]:
        sample: list[dict[str, Any]] = []
        for ck in sorted(ciks):
            if len(sample) >= max_list:
                break
            sample.append({"cik": ck, "ticker": ticker_by_cik.get(ck)})
        return {
            "name": name,
            "issuer_count": len(ciks),
            "truncated_sample": sample,
        }

    master_no_filing = master_ciks - filing_ciks
    filing_no_silver = filing_ciks - silver_ciks
    snapshot_no_factor = snap_ciks - factor_ciks
    factor_no_validation = factor_ciks - val_ciks
    validation_no_score = val_ciks - score_ciks

    snap_n = _counts_per_cik(client, "issuer_quarter_snapshots")
    factor_n = _counts_per_cik(client, "issuer_quarter_factor_panels")

    def _below(d: dict[str, int], n: int) -> list[dict[str, Any]]:
        r = [
            {
                "cik": ck,
                "ticker": ticker_by_cik.get(ck),
                "row_count": d[ck],
            }
            for ck in sorted(d, key=lambda x: (d[x], x))
            if d[ck] < n
        ]
        return r[:max_list]

    return {
        "issuer_master_no_filing_index": _rows("master_no_filing", master_no_filing),
        "filing_index_no_silver_facts": _rows("filing_no_silver", filing_no_silver),
        "snapshots_no_factor_panels": _rows("snapshot_no_factor", snapshot_no_factor),
        "factor_panels_no_validation": _rows(
            "factor_no_validation", factor_no_validation
        ),
        "validation_panels_no_state_change_score": _rows(
            "validation_no_score", validation_no_score
        ),
        "usable_quarter_count_lt2": _below(snap_n, 2),
        "usable_quarter_count_lt4": _below(snap_n, 4),
        "usable_quarter_count_lt6": _below(snap_n, 6),
        "factor_row_count_lt2": _below(factor_n, 2),
        "factor_row_count_lt4": _below(factor_n, 4),
    }
