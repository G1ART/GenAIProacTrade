"""Supabase 테이블 접근: raw/silver, issuer, filing_index, ingest_runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client


def raw_filing_exists(client: Client, *, cik: str, accession_no: str) -> bool:
    r = (
        client.table("raw_sec_filings")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_raw_filing(client: Client, row: dict[str, Any]) -> None:
    client.table("raw_sec_filings").insert(row).execute()


def silver_filing_exists(
    client: Client, *, cik: str, accession_no: str, revision_no: int
) -> bool:
    r = (
        client.table("silver_sec_filings")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("revision_no", revision_no)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_silver_filing(client: Client, row: dict[str, Any]) -> None:
    client.table("silver_sec_filings").insert(row).execute()


def upsert_issuer_master(client: Client, row: dict[str, Any]) -> None:
    """
    CIK 기준 idempotent upsert. first_seen_at / created_at 은 최초 insert 시만 고정.
    """
    cik = row["cik"]
    now_iso = row["last_seen_at"]
    r = (
        client.table("issuer_master")
        .select("id,first_seen_at,created_at")
        .eq("cik", cik)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd: dict[str, Any] = {
            "company_name": row["company_name"],
            "last_seen_at": now_iso,
            "updated_at": now_iso,
            "is_active": row.get("is_active", True),
        }
        if row.get("ticker"):
            upd["ticker"] = row["ticker"]
        if row.get("sic") is not None:
            upd["sic"] = row["sic"]
        if row.get("sic_description") is not None:
            upd["sic_description"] = row["sic_description"]
        if row.get("latest_known_exchange") is not None:
            upd["latest_known_exchange"] = row["latest_known_exchange"]
        client.table("issuer_master").update(upd).eq("id", oid).execute()
    else:
        client.table("issuer_master").insert(row).execute()


def upsert_filing_index(client: Client, row: dict[str, Any]) -> Dict[str, bool]:
    """
    (cik, accession_no) 유니크. 재실행 시 last_seen_at / 메타 갱신.
    Returns:
        {"inserted": bool, "updated": bool}
    """
    cik = row["cik"]
    acc = row["accession_no"]
    now_iso = row["last_seen_at"]
    r = (
        client.table("filing_index")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", acc)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd = {
            "form": row.get("form"),
            "filed_at": row.get("filed_at"),
            "accepted_at": row.get("accepted_at"),
            "source_url": row.get("source_url"),
            "filing_primary_document": row.get("filing_primary_document"),
            "filing_description": row.get("filing_description"),
            "is_amendment": row.get("is_amendment", False),
            "last_seen_at": now_iso,
            "updated_at": now_iso,
        }
        client.table("filing_index").update(upd).eq("id", oid).execute()
        return {"inserted": False, "updated": True}
    client.table("filing_index").insert(row).execute()
    return {"inserted": True, "updated": False}


def ingest_run_create_started(
    client: Client,
    *,
    run_type: str,
    target_count: Optional[int],
    metadata_json: dict[str, Any],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "run_type": run_type,
        "started_at": now,
        "status": "running",
        "target_count": target_count,
        "success_count": 0,
        "failure_count": 0,
        "metadata_json": metadata_json,
    }
    res = client.table("ingest_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("ingest_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def ingest_run_finalize(
    client: Client,
    *,
    run_id: str,
    status: str,
    success_count: int,
    failure_count: int,
    error_json: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {
        "completed_at": now,
        "status": status,
        "success_count": success_count,
        "failure_count": failure_count,
    }
    if error_json is not None:
        upd["error_json"] = error_json
    client.table("ingest_runs").update(upd).eq("id", run_id).execute()


def smoke_db_select_one(client: Client) -> bool:
    """연결 확인용: issuer_master 0건이어도 성공하면 True."""
    client.table("issuer_master").select("id").limit(1).execute()
    return True


def raw_xbrl_fact_exists(client: Client, *, cik: str, accession_no: str, dedupe_key: str) -> bool:
    r = (
        client.table("raw_xbrl_facts")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("dedupe_key", dedupe_key)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_raw_xbrl_fact(client: Client, row: dict[str, Any]) -> None:
    client.table("raw_xbrl_facts").insert(row).execute()


def silver_xbrl_fact_exists(
    client: Client,
    *,
    cik: str,
    accession_no: str,
    canonical_concept: str,
    revision_no: int,
    fact_period_key: str,
) -> bool:
    r = (
        client.table("silver_xbrl_facts")
        .select("id")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("canonical_concept", canonical_concept)
        .eq("revision_no", revision_no)
        .eq("fact_period_key", fact_period_key)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def insert_silver_xbrl_fact(client: Client, row: dict[str, Any]) -> None:
    client.table("silver_xbrl_facts").insert(row).execute()


def upsert_issuer_quarter_snapshot(client: Client, row: dict[str, Any]) -> Dict[str, bool]:
    cik = row["cik"]
    fy = row["fiscal_year"]
    fp = row["fiscal_period"]
    acc = row["accession_no"]
    r = (
        client.table("issuer_quarter_snapshots")
        .select("id")
        .eq("cik", cik)
        .eq("fiscal_year", fy)
        .eq("fiscal_period", fp)
        .eq("accession_no", acc)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd = {k: v for k, v in row.items() if k not in ("created_at",)}
        client.table("issuer_quarter_snapshots").update(upd).eq("id", oid).execute()
        return {"inserted": False, "updated": True}
    client.table("issuer_quarter_snapshots").insert(row).execute()
    return {"inserted": True, "updated": False}


def fetch_raw_xbrl_facts_for_filing(
    client: Client, *, cik: str, accession_no: str
) -> list[dict[str, Any]]:
    r = (
        client.table("raw_xbrl_facts")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .execute()
    )
    return list(r.data or [])


def fetch_silver_xbrl_facts_for_filing(
    client: Client, *, cik: str, accession_no: str
) -> list[dict[str, Any]]:
    r = (
        client.table("silver_xbrl_facts")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .execute()
    )
    return list(r.data or [])


def smoke_facts_db(client: Client) -> bool:
    """raw_xbrl_facts 테이블 도달 확인."""
    client.table("raw_xbrl_facts").select("id").limit(1).execute()
    return True


def fetch_cik_map_for_tickers(client: Client, tickers: list[str]) -> dict[str, Optional[str]]:
    """
    티커(대문자) -> CIK. issuer_master 일괄 조회(ingest-market-prices N+1 방지).
    청크로 나눠 PostgREST URL 한도를 피한다.
    """
    if not tickers:
        return {}
    uniq = sorted({str(t).upper().strip() for t in tickers if t and str(t).strip()})
    out: dict[str, Optional[str]] = {u: None for u in uniq}
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
            cik = row.get("cik")
            if t:
                out[t] = str(cik) if cik is not None else None
    return out


def fetch_cik_for_ticker(client: Client, *, ticker: str) -> Optional[str]:
    r = (
        client.table("issuer_master")
        .select("cik")
        .eq("ticker", ticker.upper().strip())
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return str(r.data[0]["cik"])


def fetch_issuer_quarter_snapshots_for_cik(client: Client, *, cik: str) -> list[dict[str, Any]]:
    r = client.table("issuer_quarter_snapshots").select("*").eq("cik", cik).execute()
    return list(r.data or [])


def factor_panel_exists(
    client: Client,
    *,
    cik: str,
    fiscal_year: int,
    fiscal_period: str,
    accession_no: str,
    factor_version: str,
) -> bool:
    q = (
        client.table("issuer_quarter_factor_panels")
        .select("id")
        .eq("cik", cik)
        .eq("fiscal_year", fiscal_year)
        .eq("fiscal_period", fiscal_period)
        .eq("accession_no", accession_no)
        .eq("factor_version", factor_version)
        .limit(1)
        .execute()
    )
    return bool(q.data)


def insert_factor_panel(client: Client, row: dict[str, Any]) -> None:
    client.table("issuer_quarter_factor_panels").insert(row).execute()


def fetch_factor_panels_for_cik(
    client: Client, *, cik: str, limit: int = 5
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .eq("cik", cik)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(r.data or [])


def smoke_factor_panels_db(client: Client) -> bool:
    client.table("issuer_quarter_factor_panels").select("id").limit(1).execute()
    return True


# --- Phase 4: market / universe / validation ---


def smoke_market_tables(client: Client) -> bool:
    client.table("universe_memberships").select("id").limit(1).execute()
    client.table("silver_market_prices_daily").select("id").limit(1).execute()
    return True


def smoke_validation_panel_table(client: Client) -> bool:
    client.table("factor_market_validation_panels").select("id").limit(1).execute()
    return True


def insert_universe_memberships_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    client.table("universe_memberships").insert(rows).execute()


def fetch_max_as_of_universe(client: Client, *, universe_name: str) -> Optional[str]:
    r = (
        client.table("universe_memberships")
        .select("as_of_date")
        .eq("universe_name", universe_name)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    v = r.data[0].get("as_of_date")
    return str(v)[:10] if v else None


def fetch_symbols_universe_as_of(
    client: Client, *, universe_name: str, as_of_date: str
) -> list[str]:
    r = (
        client.table("universe_memberships")
        .select("symbol")
        .eq("universe_name", universe_name)
        .eq("as_of_date", as_of_date)
        .execute()
    )
    out = [str(row["symbol"]).upper().strip() for row in (r.data or [])]
    return sorted(set(out))


def upsert_market_symbol_registry(client: Client, row: dict[str, Any]) -> None:
    sym = str(row["symbol"]).upper().strip()
    row = {**row, "symbol": sym}
    r = (
        client.table("market_symbol_registry")
        .select("id,first_seen_at")
        .eq("symbol", sym)
        .limit(1)
        .execute()
    )
    if r.data:
        oid = r.data[0]["id"]
        upd = {k: v for k, v in row.items() if k not in ("id", "created_at", "first_seen_at")}
        client.table("market_symbol_registry").update(upd).eq("id", oid).execute()
    else:
        client.table("market_symbol_registry").insert(row).execute()


def fetch_ticker_for_cik(client: Client, *, cik: str) -> Optional[str]:
    q = (
        client.table("issuer_master")
        .select("ticker")
        .eq("cik", cik)
        .limit(1)
        .execute()
    )
    if not q.data or not q.data[0].get("ticker"):
        return None
    return str(q.data[0]["ticker"]).upper().strip()


def upsert_raw_market_prices_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    client.table("raw_market_prices_daily").upsert(
        rows, on_conflict="symbol,trade_date,source_name"
    ).execute()


def upsert_silver_market_prices_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    client.table("silver_market_prices_daily").upsert(
        rows, on_conflict="symbol,trade_date"
    ).execute()


def fetch_silver_prices_for_symbol_range(
    client: Client,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    sym = symbol.upper().strip()
    r = (
        client.table("silver_market_prices_daily")
        .select("*")
        .eq("symbol", sym)
        .gte("trade_date", start_date)
        .lte("trade_date", end_date)
        .order("trade_date")
        .execute()
    )
    return list(r.data or [])


def upsert_market_metadata_latest(client: Client, row: dict[str, Any]) -> None:
    if not row:
        return
    client.table("market_metadata_latest").upsert(
        row, on_conflict="symbol,source_name"
    ).execute()


def upsert_risk_free_rates_batch(
    client: Client,
    rows: list[dict[str, Any]],
    *,
    chunk_size: int = 200,
) -> None:
    """행이 많을 때 단일 요청이 장시간 걸리지 않도록 청크 upsert."""
    if not rows:
        return
    step = max(1, chunk_size)
    for i in range(0, len(rows), step):
        chunk = rows[i : i + step]
        client.table("risk_free_rates_daily").upsert(
            chunk, on_conflict="rate_date,source_name"
        ).execute()


def fetch_risk_free_range(
    client: Client, *, start_date: str, end_date: str, source_name: str
) -> list[dict[str, Any]]:
    r = (
        client.table("risk_free_rates_daily")
        .select("rate_date,annualized_rate")
        .eq("source_name", source_name)
        .gte("rate_date", start_date)
        .lte("rate_date", end_date)
        .order("rate_date")
        .execute()
    )
    return list(r.data or [])


def upsert_forward_return_row(client: Client, row: dict[str, Any]) -> None:
    client.table("forward_returns_daily_horizons").upsert(
        row, on_conflict="symbol,signal_date,horizon_type"
    ).execute()


def fetch_quarter_snapshot_by_accession(
    client: Client, *, cik: str, accession_no: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_snapshots")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_factor_panels_all(
    client: Client, *, limit: int = 5000
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return list(r.data or [])


def upsert_factor_market_validation_panel(
    client: Client, row: dict[str, Any]
) -> None:
    client.table("factor_market_validation_panels").upsert(
        row, on_conflict="cik,accession_no,factor_version"
    ).execute()


def fetch_factor_market_validation_panels_for_symbols(
    client: Client, *, symbols: list[str], limit: int = 8000
) -> list[dict[str, Any]]:
    """대문자 심볼 목록으로 검증 패널 조회(배치 in_)."""
    if not symbols:
        return []
    sym_u = [s.upper().strip() for s in symbols if s and str(s).strip()]
    if not sym_u:
        return []
    out: list[dict[str, Any]] = []
    chunk_size = 80
    for i in range(0, len(sym_u), chunk_size):
        chunk = sym_u[i : i + chunk_size]
        r = (
            client.table("factor_market_validation_panels")
            .select("*")
            .in_("symbol", chunk)
            .limit(max(1, limit - len(out)))
            .execute()
        )
        out.extend(r.data or [])
        if len(out) >= limit:
            break
    return out[:limit]


def fetch_issuer_quarter_factor_panels_for_ciks(
    client: Client, *, ciks: list[str], limit: int = 8000
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """(cik, accession_no, factor_version) → 행."""
    m: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not ciks:
        return m
    uniq = sorted(set(ciks))
    chunk_size = 40
    for i in range(0, len(uniq), chunk_size):
        chunk = uniq[i : i + chunk_size]
        r = (
            client.table("issuer_quarter_factor_panels")
            .select("*")
            .in_("cik", chunk)
            .limit(limit)
            .execute()
        )
        for row in r.data or []:
            k = (str(row["cik"]), str(row["accession_no"]), str(row["factor_version"]))
            m[k] = dict(row)
    return m


def factor_validation_run_insert_started(
    client: Client,
    *,
    run_type: str,
    factor_version: str,
    universe_name: str,
    horizon_type: str,
    metadata_json: dict[str, Any],
    target_count: Optional[int],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "run_type": run_type,
        "factor_version": factor_version,
        "universe_name": universe_name,
        "horizon_type": horizon_type,
        "started_at": now,
        "status": "running",
        "target_count": target_count,
        "success_count": 0,
        "failure_count": 0,
        "metadata_json": metadata_json,
    }
    res = client.table("factor_validation_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("factor_validation_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def factor_validation_run_finalize(
    client: Client,
    *,
    run_id: str,
    status: str,
    success_count: int,
    failure_count: int,
    error_json: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {
        "completed_at": now,
        "status": status,
        "success_count": success_count,
        "failure_count": failure_count,
    }
    if error_json is not None:
        upd["error_json"] = error_json
    client.table("factor_validation_runs").update(upd).eq("id", run_id).execute()


def insert_factor_validation_summary(client: Client, row: dict[str, Any]) -> None:
    client.table("factor_validation_summaries").insert(row).execute()


def insert_factor_quantile_result(client: Client, row: dict[str, Any]) -> None:
    client.table("factor_quantile_results").insert(row).execute()


def insert_factor_coverage_report(client: Client, row: dict[str, Any]) -> None:
    client.table("factor_coverage_reports").insert(row).execute()


def smoke_research_tables(client: Client) -> None:
    client.table("factor_validation_runs").select("id").limit(1).execute()


def fetch_latest_factor_validation_summaries(
    client: Client,
    *,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
) -> tuple[Optional[str], list[dict[str, Any]]]:
    """가장 최근 completed run 기준 요약(raw+excess)."""
    r = (
        client.table("factor_validation_runs")
        .select("id,completed_at,status")
        .eq("universe_name", universe_name)
        .eq("horizon_type", horizon_type)
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None, []
    rid = str(r.data[0]["id"])
    s = (
        client.table("factor_validation_summaries")
        .select("*")
        .eq("run_id", rid)
        .eq("factor_name", factor_name)
        .execute()
    )
    return rid, list(s.data or [])


def fetch_factor_quantiles_for_run(
    client: Client,
    *,
    run_id: str,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
) -> list[dict[str, Any]]:
    q = (
        client.table("factor_quantile_results")
        .select("*")
        .eq("run_id", run_id)
        .eq("factor_name", factor_name)
        .eq("universe_name", universe_name)
        .eq("horizon_type", horizon_type)
        .eq("return_basis", return_basis)
        .order("quantile_index")
        .execute()
    )
    return list(q.data or [])


# --- Phase 6: state change (입력으로 factor_market_validation_panels 미사용) ---


def fetch_issuer_master_rows_for_tickers(
    client: Client, tickers: list[str]
) -> list[dict[str, Any]]:
    if not tickers:
        return []
    uniq: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        u = str(t).upper().strip()
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    by_ticker: dict[str, dict[str, Any]] = {}
    chunk_size = 80
    for i in range(0, len(uniq), chunk_size):
        chunk = uniq[i : i + chunk_size]
        r = (
            client.table("issuer_master")
            .select("id,cik,ticker")
            .in_("ticker", chunk)
            .execute()
        )
        for row in r.data or []:
            t = str(row.get("ticker") or "").upper().strip()
            if t:
                by_ticker[t] = dict(row)
    return [by_ticker[t] for t in uniq if t in by_ticker]


def fetch_all_factor_panels_for_cik_version(
    client: Client, *, cik: str, factor_version: str
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .eq("cik", cik)
        .eq("factor_version", factor_version)
        .execute()
    )
    return list(r.data or [])


def fetch_snapshots_by_ids(
    client: Client, ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    uniq = list({str(x) for x in ids if x})
    out: dict[str, dict[str, Any]] = {}
    chunk_size = 40
    for i in range(0, len(uniq), chunk_size):
        chunk = uniq[i : i + chunk_size]
        r = (
            client.table("issuer_quarter_snapshots")
            .select("*")
            .in_("id", chunk)
            .execute()
        )
        for row in r.data or []:
            out[str(row["id"])] = dict(row)
    return out


def state_change_run_insert_started(
    client: Client,
    *,
    run_type: str,
    universe_name: str,
    as_of_date_start: Optional[str],
    as_of_date_end: Optional[str],
    factor_version: str,
    config_version: str,
    input_snapshot_json: dict[str, Any],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "run_type": run_type,
        "universe_name": universe_name,
        "as_of_date_start": as_of_date_start,
        "as_of_date_end": as_of_date_end,
        "factor_version": factor_version,
        "config_version": config_version,
        "input_snapshot_json": input_snapshot_json,
        "row_count": 0,
        "warning_count": 0,
        "status": "running",
        "started_at": now,
    }
    res = client.table("state_change_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("state_change_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def state_change_run_finalize(
    client: Client,
    *,
    run_id: str,
    status: str,
    row_count: int,
    warning_count: int,
    error_json: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {
        "status": status,
        "finished_at": now,
        "row_count": row_count,
        "warning_count": warning_count,
    }
    if error_json is not None:
        upd["error_json"] = error_json
    client.table("state_change_runs").update(upd).eq("id", run_id).execute()


def insert_state_change_components_batch(
    client: Client, rows: list[dict[str, Any]], *, chunk_size: int = 80
) -> None:
    if not rows:
        return
    step = max(1, chunk_size)
    for i in range(0, len(rows), step):
        client.table("issuer_state_change_components").insert(rows[i : i + step]).execute()


def insert_state_change_scores_batch(
    client: Client, rows: list[dict[str, Any]], *, chunk_size: int = 80
) -> None:
    if not rows:
        return
    step = max(1, chunk_size)
    for i in range(0, len(rows), step):
        client.table("issuer_state_change_scores").insert(rows[i : i + step]).execute()


def insert_state_change_candidates_batch(
    client: Client, rows: list[dict[str, Any]], *, chunk_size: int = 80
) -> None:
    if not rows:
        return
    step = max(1, chunk_size)
    for i in range(0, len(rows), step):
        client.table("state_change_candidates").insert(rows[i : i + step]).execute()


def smoke_state_change_tables(client: Client) -> None:
    client.table("state_change_runs").select("id").limit(1).execute()


def fetch_state_change_run(client: Client, *, run_id: str) -> Optional[dict[str, Any]]:
    r = (
        client.table("state_change_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_state_change_candidate_class_counts(
    client: Client, *, run_id: str
) -> dict[str, int]:
    r = (
        client.table("state_change_candidates")
        .select("candidate_class")
        .eq("run_id", run_id)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in r.data or []:
        c = str(row.get("candidate_class") or "")
        counts[c] = counts.get(c, 0) + 1
    return counts


def fetch_latest_state_change_run_id(
    client: Client, *, universe_name: str
) -> Optional[str]:
    r = (
        client.table("state_change_runs")
        .select("id,finished_at,status")
        .eq("universe_name", universe_name)
        .eq("status", "completed")
        .order("finished_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return str(r.data[0]["id"])


def fetch_state_change_scores_for_run(
    client: Client, *, run_id: str, limit: int = 500
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_state_change_scores")
        .select("*")
        .eq("run_id", run_id)
        .order("state_change_score_v1", desc=True)
        .limit(limit)
        .execute()
    )
    return list(r.data or [])


def fetch_state_change_candidates_for_run(
    client: Client, *, run_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    r = (
        client.table("state_change_candidates")
        .select("*")
        .eq("run_id", run_id)
        .order("candidate_rank")
        .limit(limit)
        .execute()
    )
    return list(r.data or [])
