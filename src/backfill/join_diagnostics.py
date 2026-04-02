"""유니버스·issuer·filing·facts·선행·검증 조인 누락 진단 (결정적)."""

from __future__ import annotations

from typing import Any

from db.records import fetch_cik_for_ticker


def build_join_diagnostics(
    client: Any,
    *,
    symbols: list[str],
    forward_sample_limit: int = 3000,
    panel_sample_limit: int = 1500,
) -> dict[str, Any]:
    sym_set = {str(s).upper().strip() for s in symbols if str(s).strip()}
    out: dict[str, Any] = {
        "universe_symbols_checked": sorted(sym_set),
        "missing_issuer_master": [],
        "issuer_no_filing_index": [],
        "issuer_no_silver_facts": [],
        "symbol_no_forward_return_row": [],
        "cik_with_panel_but_not_in_forward_sample": [],
        "forward_row_no_validation_panel_sample": [],
    }

    cik_by_sym: dict[str, str] = {}
    for sym in sorted(sym_set):
        cik = fetch_cik_for_ticker(client, ticker=sym)
        if not cik:
            out["missing_issuer_master"].append(sym)
            continue
        cik_by_sym[sym] = cik
        fi = (
            client.table("filing_index")
            .select("id")
            .eq("cik", cik)
            .limit(1)
            .execute()
        )
        if not fi.data:
            out["issuer_no_filing_index"].append({"ticker": sym, "cik": cik})
            continue
        sf = (
            client.table("silver_xbrl_facts")
            .select("id")
            .eq("cik", cik)
            .limit(1)
            .execute()
        )
        if not sf.data:
            out["issuer_no_silver_facts"].append({"ticker": sym, "cik": cik})

    for sym, cik in sorted(cik_by_sym.items()):
        fr = (
            client.table("forward_returns_daily_horizons")
            .select("id")
            .eq("cik", cik)
            .limit(1)
            .execute()
        )
        if not fr.data:
            out["symbol_no_forward_return_row"].append({"ticker": sym, "cik": cik})

    fr_ciks: set[str] = set()
    fr_rows = (
        client.table("forward_returns_daily_horizons")
        .select("cik")
        .limit(max(100, forward_sample_limit))
        .execute()
    )
    for row in fr_rows.data or []:
        ck = row.get("cik")
        if ck:
            fr_ciks.add(str(ck))

    fp = (
        client.table("issuer_quarter_factor_panels")
        .select("cik,accession_no")
        .limit(panel_sample_limit)
        .execute()
    )
    seen: set[tuple[str, str]] = set()
    for row in fp.data or []:
        cik = str(row.get("cik") or "")
        acc = str(row.get("accession_no") or "")
        if not cik or (cik, acc) in seen:
            continue
        seen.add((cik, acc))
        if cik not in fr_ciks and len(out["cik_with_panel_but_not_in_forward_sample"]) < 40:
            im = (
                client.table("issuer_master")
                .select("ticker")
                .eq("cik", cik)
                .limit(1)
                .execute()
            )
            tkr = str(im.data[0]["ticker"]) if im.data else None
            out["cik_with_panel_but_not_in_forward_sample"].append(
                {"cik": cik, "ticker": tkr, "accession_no": acc}
            )

    fwd = (
        client.table("forward_returns_daily_horizons")
        .select("cik,symbol,signal_date")
        .limit(400)
        .execute()
    )
    for row in fwd.data or []:
        cik = row.get("cik")
        if not cik:
            continue
        vp = (
            client.table("factor_market_validation_panels")
            .select("id")
            .eq("cik", str(cik))
            .limit(1)
            .execute()
        )
        if not vp.data and len(out["forward_row_no_validation_panel_sample"]) < 40:
            out["forward_row_no_validation_panel_sample"].append(
                {
                    "cik": str(cik),
                    "symbol": row.get("symbol"),
                    "signal_date": str(row.get("signal_date")),
                }
            )

    return out


def thin_factor_issuer_report(
    client: Any,
    *,
    max_rows: int = 100,
    threshold: int = 4,
) -> list[dict[str, Any]]:
    """factor panel 행 수가 threshold 미만인 CIK (테이블 순회·메모리 집계; 대용량 시 시간 소요)."""
    rows_out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    page = 1000
    offset = 0
    while True:
        r = (
            client.table("issuer_quarter_factor_panels")
            .select("cik")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = r.data or []
        if not batch:
            break
        for row in batch:
            cik = str(row.get("cik") or "")
            if cik:
                counts[cik] = counts.get(cik, 0) + 1
        if len(batch) < page:
            break
        offset += page
    for cik, n in sorted(counts.items(), key=lambda x: (x[1], x[0])):
        if n < threshold:
            im = (
                client.table("issuer_master")
                .select("ticker")
                .eq("cik", cik)
                .limit(1)
                .execute()
            )
            tkr = str(im.data[0]["ticker"]) if im.data else None
            rows_out.append({"cik": cik, "ticker": tkr, "factor_row_count": n})
        if len(rows_out) >= max_rows:
            break
    return rows_out
