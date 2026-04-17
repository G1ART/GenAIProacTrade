"""Supabase 테이블 접근: raw/silver, issuer, filing_index, ingest_runs."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client


def normalize_sec_cik(c: Any) -> str:
    """SEC CIK 정규화: 숫자·숫자 문자열은 10자리 0패딩(issuer_master·패널 조인과 동일).

    Supabase/JSON에서 cik이 float(예: 320193.0)이면 str(c)가 '320193.0'이 되어
    isdigit()만으로는 패딩되지 않으므로 정수화 후 zfill 한다.
    """
    if c is None:
        return ""
    if isinstance(c, bool):
        return ""
    if isinstance(c, int):
        return str(abs(c)).zfill(10)
    if isinstance(c, float):
        if not math.isfinite(c):
            return ""
        iv = int(c)
        if abs(c - float(iv)) < 1e-9:
            return str(abs(iv)).zfill(10)
        return str(c).strip()
    t = str(c).strip()
    if not t:
        return t
    if t.isdigit():
        return t.zfill(10)
    try:
        fv = float(t)
        if math.isfinite(fv):
            iv = int(fv)
            if abs(fv - float(iv)) < 1e-9:
                return str(abs(iv)).zfill(10)
    except ValueError:
        pass
    return t


def issuer_quarter_factor_panel_join_key(
    cik: Any,
    accession_no: Any,
    factor_version: Any,
    *,
    default_factor_version: str = "v1",
) -> tuple[str, str, str]:
    """issuer_quarter_factor_panels ↔ factor_market_validation_panels 조인 키.

    PostgREST/레거시 행에서 ``factor_version``이 빈 문자열이거나 공백만 있는 경우,
    ``fp_map`` 키와 ``fp_for`` 조회 쪽 규칙이 어긋나 전 행 미스매치(커버리지 0)가
    나지 않도록 한 곳에서 정규화한다.
    """
    d = (default_factor_version or "v1").strip() or "v1"
    if factor_version is None:
        fv = d
    else:
        fv = str(factor_version).strip()
        if not fv:
            fv = d
    acc = str(accession_no or "").strip()
    return (normalize_sec_cik(cik), acc, fv)


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


def fetch_filing_index_rows_for_cik(
    client: Client,
    *,
    cik: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Phase 41 falsifier substrate: recent filing_index rows for a CIK (filed_at desc).
    `cik` should match table storage (typically zero-padded 10 digits).
    """
    ck = str(cik or "").strip()
    if not ck:
        return []
    lim = max(1, min(int(limit), 500))
    r = (
        client.table("filing_index")
        .select("*")
        .eq("cik", ck)
        .order("filed_at", desc=True)
        .limit(lim)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


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


def fetch_raw_xbrl_fact_dedupe_keys_for_filing(
    client: Client,
    *,
    cik: str,
    accession_no: str,
    page_size: int = 1000,
) -> set[str]:
    """Return the set of already-ingested ``dedupe_key`` values for one filing.

    Backfill speed: avoids N-per-fact SELECTs by hydrating the dedupe index with
    at most ``ceil(n_existing / page_size)`` requests; callers drive bulk insert
    through this set.
    """
    keys: set[str] = set()
    offset = 0
    while True:
        r = (
            client.table("raw_xbrl_facts")
            .select("dedupe_key")
            .eq("cik", cik)
            .eq("accession_no", accession_no)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = list(r.data or [])
        if not batch:
            break
        for row in batch:
            dk = row.get("dedupe_key")
            if dk:
                keys.add(str(dk))
        if len(batch) < page_size:
            break
        offset += page_size
    return keys


def insert_raw_xbrl_facts_bulk(
    client: Client,
    rows: list[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> int:
    """Chunked bulk insert for ``raw_xbrl_facts``. Returns total rows inserted.

    Caller must ensure ``rows`` contains only new records (pre-filtered against
    :func:`fetch_raw_xbrl_fact_dedupe_keys_for_filing`).
    """
    if not rows:
        return 0
    if chunk_size <= 0:
        chunk_size = len(rows)
    inserted = 0
    for i in range(0, len(rows), chunk_size):
        batch = rows[i : i + chunk_size]
        client.table("raw_xbrl_facts").insert(batch).execute()
        inserted += len(batch)
    return inserted


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


def fetch_silver_xbrl_fact_keys_for_filing(
    client: Client,
    *,
    cik: str,
    accession_no: str,
    page_size: int = 1000,
) -> set[tuple[str, int, str]]:
    """Return the existing ``(canonical_concept, revision_no, fact_period_key)`` tuples for one filing."""
    keys: set[tuple[str, int, str]] = set()
    offset = 0
    while True:
        r = (
            client.table("silver_xbrl_facts")
            .select("canonical_concept, revision_no, fact_period_key")
            .eq("cik", cik)
            .eq("accession_no", accession_no)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = list(r.data or [])
        if not batch:
            break
        for row in batch:
            try:
                k = (
                    str(row.get("canonical_concept") or ""),
                    int(row.get("revision_no") or 0),
                    str(row.get("fact_period_key") or ""),
                )
            except (TypeError, ValueError):
                continue
            keys.add(k)
        if len(batch) < page_size:
            break
        offset += page_size
    return keys


def insert_silver_xbrl_facts_bulk(
    client: Client,
    rows: list[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> int:
    """Chunked bulk insert for ``silver_xbrl_facts``. Returns total rows inserted."""
    if not rows:
        return 0
    if chunk_size <= 0:
        chunk_size = len(rows)
    inserted = 0
    for i in range(0, len(rows), chunk_size):
        batch = rows[i : i + chunk_size]
        client.table("silver_xbrl_facts").insert(batch).execute()
        inserted += len(batch)
    return inserted


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


def fetch_universe_memberships_for_as_of(
    client: Client,
    *,
    universe_name: str,
    as_of_date: str,
) -> list[dict[str, Any]]:
    r = (
        client.table("universe_memberships")
        .select("symbol,cik,source_payload_json")
        .eq("universe_name", universe_name)
        .eq("as_of_date", as_of_date)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_market_symbol_registry_rows_for_symbols(
    client: Client,
    symbols: list[str],
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    uniq: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        u = str(s).upper().strip()
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    out: dict[str, dict[str, Any]] = {}
    step = 120
    for i in range(0, len(uniq), step):
        part = uniq[i : i + step]
        r = (
            client.table("market_symbol_registry")
            .select("*")
            .in_("symbol", part)
            .execute()
        )
        for row in r.data or []:
            sym = str(row.get("symbol") or "").upper().strip()
            if sym:
                out[sym] = dict(row)
    return out


def fetch_market_symbol_registry_symbols_by_ciks(
    client: Client,
    ciks: list[str],
) -> dict[str, list[str]]:
    """정규화 CIK -> 레지스트리에 등록된 티커 목록."""
    if not ciks:
        return {}
    uniq = sorted({str(c).strip() for c in ciks if c and str(c).strip()})
    by_cik: dict[str, list[str]] = {}
    step = 80
    for i in range(0, len(uniq), step):
        part = uniq[i : i + step]
        r = (
            client.table("market_symbol_registry")
            .select("symbol,cik")
            .in_("cik", part)
            .execute()
        )
        for row in r.data or []:
            ck = str(row.get("cik") or "").strip()
            sym = str(row.get("symbol") or "").upper().strip()
            if not ck or not sym:
                continue
            by_cik.setdefault(ck, []).append(sym)
    for ck in by_cik:
        by_cik[ck] = sorted(set(by_cik[ck]))
    return by_cik


def fetch_issuer_master_ciks_present(
    client: Client,
    ciks: list[str],
) -> set[str]:
    """issuer_master 에 실제 존재하는 CIK 집합(숫자형은 10자리 정규화로 조회)."""

    if not ciks:
        return set()
    uniq = sorted(
        {
            normalize_sec_cik(c)
            for c in ciks
            if c and str(c).strip() and normalize_sec_cik(c)
        }
    )
    present: set[str] = set()
    step = 80
    for i in range(0, len(uniq), step):
        part = uniq[i : i + step]
        r = (
            client.table("issuer_master")
            .select("cik")
            .in_("cik", part)
            .execute()
        )
        for row in r.data or []:
            ck = str(row.get("cik") or "").strip()
            if ck:
                present.add(ck)
    return present


def pick_best_market_metadata_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    동일 심볼에 복수 행일 때: as_of_date 내림차순, 동률이면 유동성 필드가 채워진 행 우선.
    검증 패널 빌드·메타 갭 드라이버가 동일 규칙을 쓰도록 공유한다(Phase 29).
    """
    if not rows:
        return None

    def _key(r: dict[str, Any]) -> tuple[str, int, int]:
        asof = str(r.get("as_of_date") or "")
        liq = 1 if r.get("avg_daily_volume") is not None else 0
        mc = 1 if r.get("market_cap") is not None else 0
        return (asof, liq, mc)

    best = max(rows, key=_key)
    return dict(best)


def fetch_market_metadata_latest_row_deterministic(
    client: Client, *, symbol: str
) -> dict[str, Any] | None:
    """심볼당 market_metadata_latest 전 행을 읽은 뒤 pick_best 로 1건 선택."""
    u = str(symbol).upper().strip()
    if not u:
        return None
    r = client.table("market_metadata_latest").select("*").eq("symbol", u).execute()
    rows = [dict(x) for x in (r.data or [])]
    return pick_best_market_metadata_row(rows)


def fetch_market_metadata_latest_rows_for_symbols(
    client: Client,
    symbols: list[str],
) -> dict[str, dict[str, Any]]:
    """심볼당 결정적 1건: as_of 내림차순·유동성 우선(`pick_best_market_metadata_row`)."""
    if not symbols:
        return {}
    uniq: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        u = str(s).upper().strip()
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    rows_by_sym: dict[str, list[dict[str, Any]]] = {u: [] for u in uniq}
    step = 100
    for i in range(0, len(uniq), step):
        part = uniq[i : i + step]
        r = (
            client.table("market_metadata_latest")
            .select("*")
            .in_("symbol", part)
            .execute()
        )
        for row in r.data or []:
            sym = str(row.get("symbol") or "").upper().strip()
            if sym in rows_by_sym:
                rows_by_sym[sym].append(dict(row))
    best: dict[str, dict[str, Any]] = {}
    for sym, rows in rows_by_sym.items():
        if not rows:
            continue
        picked = pick_best_market_metadata_row(rows)
        if picked:
            best[sym] = picked
    return best


def fetch_issuer_quarter_factor_panel_one(
    client: Client,
    *,
    cik: str,
    accession_no: str,
    factor_version: str,
) -> dict[str, Any] | None:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("factor_version", factor_version)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_factor_market_validation_panel_one(
    client: Client,
    *,
    cik: str,
    accession_no: str,
    factor_version: str,
) -> dict[str, Any] | None:
    r = (
        client.table("factor_market_validation_panels")
        .select("*")
        .eq("cik", cik)
        .eq("accession_no", accession_no)
        .eq("factor_version", factor_version)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


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


def upsert_factor_panel(client: Client, row: dict[str, Any]) -> None:
    """(cik, fiscal_year, fiscal_period, accession_no, factor_version) 충돌 시 전 행 갱신."""
    client.table("issuer_quarter_factor_panels").upsert(
        row,
        on_conflict="cik,fiscal_year,fiscal_period,accession_no,factor_version",
    ).execute()


def fetch_factor_panel_by_identity(
    client: Client,
    *,
    cik: str,
    fiscal_year: int,
    fiscal_period: str,
    accession_no: str,
    factor_version: str,
) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_quarter_factor_panels")
        .select("*")
        .eq("cik", cik)
        .eq("fiscal_year", fiscal_year)
        .eq("fiscal_period", fiscal_period)
        .eq("accession_no", accession_no)
        .eq("factor_version", factor_version)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


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


def _universe_names_from_memberships_recent_sample(
    client: Client, *, max_rows: int = 50_000
) -> set[str]:
    """최근 적재 위주로 universe_name 수집(전체 DISTINCT 대용량 스캔 대신 운영 힌트용)."""
    names: set[str] = set()
    page = min(2000, max_rows)
    offset = 0
    while offset < max_rows:
        r = (
            client.table("universe_memberships")
            .select("universe_name")
            .order("created_at", desc=True)
            .range(offset, offset + page - 1)
            .execute()
        )
        rows = r.data or []
        if not rows:
            break
        for row in rows:
            u = str(row.get("universe_name") or "").strip()
            if u:
                names.add(u)
        if len(rows) < page:
            break
        offset += page
    return names


def fetch_universe_catalog_for_operators(client: Client) -> list[dict[str, Any]]:
    """
    CLI용: 어떤 --universe 문자열을 써야 하는지 안내.
    표준 슬라이스 + research_programs/state_change_runs/멤버십 샘플에서 이름을 모은 뒤
    멤버십 최신 as_of·심볼 수를 채운다.
    """
    # `research.universe_slices.ALL_RESEARCH_SLICES` 와 동일(레이어 순환 방지 위해 중복).
    names: set[str] = {
        "sp500_current",
        "sp500_proxy_candidates_v1",
        "combined_largecap_research_v1",
    }
    names |= _universe_names_from_memberships_recent_sample(client)
    try:
        r = client.table("research_programs").select("universe_name").execute()
        for row in r.data or []:
            u = str(row.get("universe_name") or "").strip()
            if u:
                names.add(u)
    except Exception:
        pass
    try:
        r2 = (
            client.table("state_change_runs")
            .select("universe_name")
            .order("created_at", desc=True)
            .limit(300)
            .execute()
        )
        for row in r2.data or []:
            u = str(row.get("universe_name") or "").strip()
            if u:
                names.add(u)
    except Exception:
        pass

    out: list[dict[str, Any]] = []
    for un in sorted(names):
        m = fetch_max_as_of_universe(client, universe_name=un)
        if m:
            syms = fetch_symbols_universe_as_of(
                client, universe_name=un, as_of_date=m
            )
            out.append(
                {
                    "universe_name": un,
                    "has_membership_rows": True,
                    "latest_as_of_date": m,
                    "symbol_count_at_latest_as_of": len(syms),
                }
            )
        else:
            out.append(
                {
                    "universe_name": un,
                    "has_membership_rows": False,
                    "latest_as_of_date": None,
                    "symbol_count_at_latest_as_of": 0,
                    "note": (
                        "universe_memberships 에 해당 이름으로 행이 없음. "
                        "`refresh-universe`(sp500_current) 또는 `build-candidate-universe` 등을 먼저 실행."
                    ),
                }
            )
    return out


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


def fetch_tickers_for_ciks(
    client: Client, ciks: list[str]
) -> dict[str, Optional[str]]:
    """
    norm_cik -> canonical ticker (대문자). `ciks`는 DB `issuer_master.cik`와 동일한 문자열(원본)이어야 한다.
    청크 `in_` 조회만 사용 (CIK당 REST 1회 금지).
    """
    from collections import defaultdict

    from research_validation.metrics import norm_cik

    uniq_raw: list[str] = []
    seen: set[str] = set()
    for c in ciks:
        s = str(c).strip() if c is not None else ""
        if not s or s in seen:
            continue
        seen.add(s)
        uniq_raw.append(s)

    by_norm: dict[str, list[str]] = defaultdict(list)
    if not uniq_raw:
        return {}

    chunk_size = 80
    for i in range(0, len(uniq_raw), chunk_size):
        part = uniq_raw[i : i + chunk_size]
        r = (
            client.table("issuer_master")
            .select("cik,ticker")
            .in_("cik", part)
            .execute()
        )
        for row in r.data or []:
            raw_cik = str(row.get("cik") or "").strip()
            nc = norm_cik(raw_cik)
            t = row.get("ticker")
            if nc and t:
                by_norm[nc].append(str(t).upper().strip())

    out: dict[str, Optional[str]] = {}
    for nc, ticks in by_norm.items():
        out[nc] = sorted(ticks)[0] if ticks else None
    return out


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
    """PostgREST 페이지 상한을 넘길 수 있도록 range 로 순회."""
    out: list[dict[str, Any]] = []
    page = min(500, max(1, limit))
    offset = 0
    while len(out) < limit:
        r = (
            client.table("issuer_quarter_factor_panels")
            .select("*")
            .order("created_at", desc=False)
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = list(r.data or [])
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out[:limit]


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
            k = issuer_quarter_factor_panel_join_key(
                row.get("cik"),
                row.get("accession_no"),
                row.get("factor_version"),
                default_factor_version="v1",
            )
            m[k] = dict(row)
    return m


def fetch_issuer_quarter_factor_panels_for_accessions(
    client: Client,
    *,
    accession_nos: list[str],
    limit_per_batch: int = 8000,
    chunk_size: int = 100,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """(cik, accession_no, factor_version) → 행.

    `factor_market_validation_panels`와 조인할 때는 CIK만으로 ``limit`` 조회하면
    동일 CIK의 다른 분기 행만 먼저 채워져 스냅샷 키가 빠질 수 있어,
    검증 슬라이스에 등장하는 ``accession_no``로 직접 조회하는 편이 안전하다.
    """
    m: dict[tuple[str, str, str], dict[str, Any]] = {}
    uniq = sorted({str(a).strip() for a in accession_nos if a and str(a).strip()})
    if not uniq:
        return m
    for i in range(0, len(uniq), max(1, chunk_size)):
        batch = uniq[i : i + chunk_size]
        r = (
            client.table("issuer_quarter_factor_panels")
            .select("*")
            .in_("accession_no", batch)
            .limit(max(1, limit_per_batch))
            .execute()
        )
        for row in r.data or []:
            k = issuer_quarter_factor_panel_join_key(
                row.get("cik"),
                row.get("accession_no"),
                row.get("factor_version"),
                default_factor_version="v1",
            )
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


def fetch_latest_factor_validation_run_id(
    client: Client, *, universe_name: str, horizon_type: str
) -> Optional[str]:
    r = (
        client.table("factor_validation_runs")
        .select("id")
        .eq("universe_name", universe_name)
        .eq("horizon_type", horizon_type)
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return str(r.data[0]["id"])


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


def fetch_state_change_runs_for_universe_recent(
    client: Client, *, universe_name: str, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("state_change_runs")
        .select("*")
        .eq("universe_name", universe_name.strip())
        .order("finished_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_ingest_runs_by_run_types_recent(
    client: Client, *, run_types: list[str], limit: int = 80
) -> list[dict[str, Any]]:
    if not run_types:
        return []
    r = (
        client.table("ingest_runs")
        .select("*")
        .in_("run_type", run_types)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


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


def fetch_state_change_gating_and_candidate_count(
    client: Client, *, run_id: str, select_limit: int = 8000
) -> tuple[int, int]:
    """
    Returns (gating_high_missingness_count, total_candidates) for a state_change run.
    Client-side count for portability (Supabase postgREST without raw SQL).
    """
    r = (
        client.table("state_change_candidates")
        .select("excluded_reason")
        .eq("run_id", run_id)
        .limit(select_limit)
        .execute()
    )
    rows = list(r.data or [])
    n = len(rows)
    gating = sum(
        1
        for row in rows
        if str(row.get("excluded_reason") or "") == "gating_high_missingness"
    )
    return gating, n


def insert_public_core_cycle_quality_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_core_cycle_quality_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_core_cycle_quality_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_public_core_cycle_quality_runs_recent(
    client: Client, *, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("public_core_cycle_quality_runs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_public_core_cycle_quality_runs_for_universe(
    client: Client, *, universe_name: str, limit: int = 40
) -> list[dict[str, Any]]:
    r = (
        client.table("public_core_cycle_quality_runs")
        .select("*")
        .eq("universe_name", universe_name)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


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


# --- Backfill orchestration (20250408100000) ---


def smoke_backfill_tables(client: Client) -> None:
    client.table("backfill_orchestration_runs").select("id").limit(1).execute()


def rpc_backfill_coverage_counts(client: Client) -> Optional[dict[str, Any]]:
    try:
        r = client.rpc("backfill_coverage_counts").execute()
        if r.data is None:
            return None
        if isinstance(r.data, dict):
            return dict(r.data)
        return None
    except Exception:
        return None


def backfill_orch_insert_started(
    client: Client,
    *,
    mode: str,
    universe_name: str,
    requested_symbol_count: Optional[int],
    resolved_symbol_count: Optional[int],
    config_json: dict[str, Any],
) -> str:
    row: dict[str, Any] = {
        "mode": mode,
        "universe_name": universe_name,
        "requested_symbol_count": requested_symbol_count,
        "resolved_symbol_count": resolved_symbol_count,
        "status": "running",
        "config_json": config_json,
    }
    res = client.table("backfill_orchestration_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("backfill_orchestration_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def backfill_orch_finalize(
    client: Client,
    *,
    run_id: str,
    status: str,
    summary_json: Optional[dict[str, Any]] = None,
    error_json: Optional[dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {
        "status": status,
        "finished_at": now,
    }
    if summary_json is not None:
        upd["summary_json"] = summary_json
    if error_json is not None:
        upd["error_json"] = error_json
    client.table("backfill_orchestration_runs").update(upd).eq("id", run_id).execute()


def insert_backfill_stage_event(
    client: Client,
    *,
    orchestration_run_id: str,
    stage_name: str,
    stage_status: str,
    inserted_rows: int = 0,
    updated_rows: int = 0,
    skipped_rows: int = 0,
    warning_count: int = 0,
    error_count: int = 0,
    notes_json: Optional[dict[str, Any]] = None,
) -> None:
    row: dict[str, Any] = {
        "orchestration_run_id": orchestration_run_id,
        "stage_name": stage_name,
        "stage_status": stage_status,
        "inserted_rows": inserted_rows,
        "updated_rows": updated_rows,
        "skipped_rows": skipped_rows,
        "warning_count": warning_count,
        "error_count": error_count,
        "notes_json": notes_json or {},
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("backfill_stage_events").insert(row).execute()


def fetch_backfill_orchestration_run(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("backfill_orchestration_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_latest_backfill_orchestration(
    client: Client, *, universe_name: Optional[str] = None
) -> Optional[dict[str, Any]]:
    q = client.table("backfill_orchestration_runs").select("*")
    if universe_name:
        q = q.eq("universe_name", universe_name)
    r = q.order("started_at", desc=True).limit(1).execute()
    if not r.data:
        return None
    return dict(r.data[0])


# --- Phase 7 AI Harness (overlay) ---


def smoke_harness_tables(client: Client) -> None:
    client.table("ai_harness_candidate_inputs").select("id").limit(1).execute()


def fetch_state_change_candidate(
    client: Client, *, candidate_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("state_change_candidates")
        .select("*")
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def upsert_ai_harness_candidate_input(
    client: Client,
    *,
    candidate_id: str,
    state_change_run_id: str,
    contract_version: str,
    payload_json: dict[str, Any],
    payload_hash: str,
) -> str:
    row: dict[str, Any] = {
        "candidate_id": candidate_id,
        "state_change_run_id": state_change_run_id,
        "contract_version": contract_version,
        "payload_json": payload_json,
        "payload_hash": payload_hash,
    }
    res = (
        client.table("ai_harness_candidate_inputs")
        .upsert(row, on_conflict="candidate_id,contract_version")
        .execute()
    )
    if not res.data:
        raise RuntimeError("ai_harness_candidate_inputs upsert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_ai_harness_input_for_candidate(
    client: Client, *, candidate_id: str, contract_version: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("ai_harness_candidate_inputs")
        .select("*")
        .eq("candidate_id", candidate_id)
        .eq("contract_version", contract_version)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_ai_harness_inputs_for_run(
    client: Client, *, run_id: str, limit: int = 500
) -> list[dict[str, Any]]:
    r = (
        client.table("ai_harness_candidate_inputs")
        .select("*")
        .eq("state_change_run_id", run_id)
        .order("built_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_max_memo_version(client: Client, *, candidate_id: str) -> int:
    r = (
        client.table("investigation_memos")
        .select("memo_version")
        .eq("candidate_id", candidate_id)
        .order("memo_version", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return 0
    return int(r.data[0]["memo_version"])


def fetch_latest_memo_for_candidate(
    client: Client, *, candidate_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("investigation_memos")
        .select("*")
        .eq("candidate_id", candidate_id)
        .order("memo_version", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_investigation_memo(
    client: Client,
    *,
    candidate_id: str,
    input_id: Optional[str],
    memo_version: int,
    generation_mode: str,
    memo_json: dict[str, Any],
    referee_passed: bool,
    referee_flags_json: list[Any],
    input_payload_hash: Optional[str] = None,
) -> str:
    row: dict[str, Any] = {
        "candidate_id": candidate_id,
        "input_id": input_id,
        "memo_version": memo_version,
        "generation_mode": generation_mode,
        "memo_json": memo_json,
        "referee_passed": referee_passed,
        "referee_flags_json": referee_flags_json,
    }
    if input_payload_hash is not None:
        row["input_payload_hash"] = input_payload_hash
    res = client.table("investigation_memos").insert(row).execute()
    if not res.data:
        raise RuntimeError("investigation_memos insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_investigation_memo(
    client: Client,
    *,
    memo_id: str,
    input_id: Optional[str],
    memo_json: dict[str, Any],
    referee_passed: bool,
    referee_flags_json: list[Any],
    input_payload_hash: Optional[str] = None,
) -> None:
    patch: dict[str, Any] = {
        "memo_json": memo_json,
        "referee_passed": referee_passed,
        "referee_flags_json": referee_flags_json,
    }
    if input_id is not None:
        patch["input_id"] = input_id
    if input_payload_hash is not None:
        patch["input_payload_hash"] = input_payload_hash
    client.table("investigation_memos").update(patch).eq("id", memo_id).execute()


def delete_investigation_memo_claims_for_memo(client: Client, *, memo_id: str) -> None:
    client.table("investigation_memo_claims").delete().eq("memo_id", memo_id).execute()


def insert_investigation_memo_claims_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 80
    for i in range(0, len(rows), step):
        client.table("investigation_memo_claims").insert(rows[i : i + step]).execute()


def fetch_investigation_memo_claims(
    client: Client, *, memo_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("investigation_memo_claims")
        .select("*")
        .eq("memo_id", memo_id)
        .order("claim_id")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_operator_review_queue_row(
    client: Client, *, candidate_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("operator_review_queue")
        .select("*")
        .eq("candidate_id", candidate_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def update_operator_review_queue_status(
    client: Client,
    *,
    candidate_id: str,
    status: str,
    status_reason: Optional[str] = None,
    memo_id: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    patch: dict[str, Any] = {"status": status, "updated_at": now}
    if status_reason is not None:
        patch["status_reason"] = status_reason
    if memo_id is not None:
        patch["memo_id"] = memo_id
    if status == "reviewed":
        patch["reviewed_at"] = now
    client.table("operator_review_queue").update(patch).eq("candidate_id", candidate_id).execute()


def upsert_operator_review_queue(
    client: Client,
    *,
    candidate_id: str,
    issuer_id: Optional[str],
    cik: str,
    as_of_date: str,
    status: str,
    memo_id: Optional[str],
    status_reason: Optional[str] = None,
) -> None:
    row: dict[str, Any] = {
        "candidate_id": candidate_id,
        "issuer_id": issuer_id,
        "cik": cik,
        "as_of_date": as_of_date,
        "status": status,
        "memo_id": memo_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status_reason is not None:
        row["status_reason"] = status_reason
    client.table("operator_review_queue").upsert(row, on_conflict="candidate_id").execute()


def fetch_operator_review_queue(
    client: Client, *, status: Optional[str] = None, limit: int = 200
) -> list[dict[str, Any]]:
    q = client.table("operator_review_queue").select("*")
    if status:
        q = q.eq("status", status)
    r = q.order("as_of_date", desc=True).limit(limit).execute()
    return [dict(x) for x in (r.data or [])]


# --- Phase 8: outlier casebook + daily scanner ---


def smoke_phase8_tables(client: Client) -> None:
    client.table("outlier_casebook_entries").select("id").limit(1).execute()
    client.table("scanner_runs").select("id").limit(1).execute()


def fetch_state_change_score_for_cik_date(
    client: Client, *, run_id: str, cik: str, as_of_date: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("issuer_state_change_scores")
        .select("*")
        .eq("run_id", run_id)
        .eq("cik", cik)
        .eq("as_of_date", as_of_date)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_state_change_components_for_cik_date(
    client: Client, *, run_id: str, cik: str, as_of_date: str, limit: int = 300
) -> list[dict[str, Any]]:
    r = (
        client.table("issuer_state_change_components")
        .select("*")
        .eq("run_id", run_id)
        .eq("cik", cik)
        .eq("as_of_date", as_of_date)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_validation_panel_best_before(
    client: Client, *, cik: str, as_of_date: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("factor_market_validation_panels")
        .select("*")
        .eq("cik", cik)
        .not_.is_("signal_available_date", "null")
        .lte("signal_available_date", as_of_date)
        .order("signal_available_date", desc=True)
        .limit(1)
        .execute()
    )
    if r.data:
        return dict(r.data[0])
    r2 = (
        client.table("factor_market_validation_panels")
        .select("*")
        .eq("cik", cik)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if r2.data:
        return dict(r2.data[0])
    return None


def fetch_forward_return_for_signal(
    client: Client,
    *,
    symbol: str,
    signal_date: str,
    horizon_type: str = "next_month",
) -> Optional[dict[str, Any]]:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    r = (
        client.table("forward_returns_daily_horizons")
        .select("*")
        .eq("symbol", sym)
        .eq("signal_date", signal_date)
        .eq("horizon_type", horizon_type)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_issuer_company_name(
    client: Client, *, issuer_id: Optional[Any]
) -> str:
    if not issuer_id:
        return ""
    r = (
        client.table("issuer_master")
        .select("company_name")
        .eq("id", str(issuer_id))
        .limit(1)
        .execute()
    )
    if not r.data:
        return ""
    return str(r.data[0].get("company_name") or "")


def insert_outlier_casebook_run(
    client: Client,
    *,
    state_change_run_id: str,
    universe_name: str,
    detection_logic_version: str,
    policy_json: dict[str, Any],
) -> str:
    row: dict[str, Any] = {
        "state_change_run_id": state_change_run_id,
        "universe_name": universe_name,
        "detection_logic_version": detection_logic_version,
        "policy_json": policy_json,
        "entries_created": 0,
    }
    res = client.table("outlier_casebook_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("outlier_casebook_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def finalize_outlier_casebook_run(
    client: Client, *, casebook_run_id: str, entries_created: int
) -> None:
    client.table("outlier_casebook_runs").update(
        {"entries_created": entries_created}
    ).eq("id", casebook_run_id).execute()


def insert_outlier_casebook_entries_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 40
    for i in range(0, len(rows), step):
        client.table("outlier_casebook_entries").insert(rows[i : i + step]).execute()


def fetch_outlier_casebook_entries_for_run(
    client: Client, *, casebook_run_id: str, limit: int = 500
) -> list[dict[str, Any]]:
    r = (
        client.table("outlier_casebook_entries")
        .select("*")
        .eq("casebook_run_id", casebook_run_id)
        .order("outlier_severity", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_latest_outlier_casebook_run(
    client: Client, *, state_change_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("outlier_casebook_runs")
        .select("*")
        .eq("state_change_run_id", state_change_run_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_scanner_run(
    client: Client,
    *,
    as_of_calendar_date: str,
    state_change_run_id: str,
    universe_name: str,
    policy_json: dict[str, Any],
) -> str:
    row: dict[str, Any] = {
        "as_of_calendar_date": as_of_calendar_date,
        "state_change_run_id": state_change_run_id,
        "universe_name": universe_name,
        "policy_json": policy_json,
        "status": "completed",
    }
    res = client.table("scanner_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("scanner_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def insert_daily_signal_snapshot(
    client: Client, *, scanner_run_id: str, stats_json: dict[str, Any]
) -> str:
    row = {"scanner_run_id": scanner_run_id, "stats_json": stats_json}
    res = client.table("daily_signal_snapshots").insert(row).execute()
    if not res.data:
        raise RuntimeError("daily_signal_snapshots insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def insert_daily_watchlist_entries_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 40
    for i in range(0, len(rows), step):
        client.table("daily_watchlist_entries").insert(rows[i : i + step]).execute()


def fetch_latest_scanner_run(
    client: Client, *, universe_name: Optional[str] = None
) -> Optional[dict[str, Any]]:
    q = client.table("scanner_runs").select("*")
    if universe_name:
        q = q.eq("universe_name", universe_name)
    r = q.order("created_at", desc=True).limit(1).execute()
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_watchlist_for_scanner(
    client: Client, *, scanner_run_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    r = (
        client.table("daily_watchlist_entries")
        .select("*")
        .eq("scanner_run_id", scanner_run_id)
        .order("priority_rank")
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_scanner_run(client: Client, *, scanner_run_id: str) -> Optional[dict[str, Any]]:
    r = (
        client.table("scanner_runs")
        .select("*")
        .eq("id", scanner_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_daily_snapshot_for_scanner(
    client: Client, *, scanner_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("daily_signal_snapshots")
        .select("*")
        .eq("scanner_run_id", scanner_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


# --- Phase 9: observability + research registry ---


def smoke_phase9_observability_tables(client: Client) -> None:
    client.table("operational_runs").select("id").limit(1).execute()
    client.table("hypothesis_registry").select("id").limit(1).execute()


def insert_operational_run_started(
    client: Client,
    *,
    run_type: str,
    component: str,
    metadata_json: dict[str, Any],
    linked_external_id: Optional[str] = None,
) -> str:
    row: dict[str, Any] = {
        "run_type": run_type,
        "component": component,
        "status": "running",
        "metadata_json": metadata_json,
        "tokens_used": None,
    }
    if linked_external_id:
        row["linked_external_id"] = linked_external_id
    res = client.table("operational_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("operational_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def finalize_operational_run(
    client: Client,
    *,
    operational_run_id: str,
    status: str,
    duration_ms: int,
    rows_read: Optional[int],
    rows_written: Optional[int],
    warnings_count: int,
    error_class: Optional[str],
    error_code: Optional[str],
    error_message_summary: Optional[str],
    trace_json: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    patch: dict[str, Any] = {
        "finished_at": now,
        "duration_ms": duration_ms,
        "status": status,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "warnings_count": warnings_count,
        "error_class": error_class,
        "error_code": error_code,
        "error_message_summary": error_message_summary,
        "trace_json": trace_json,
    }
    client.table("operational_runs").update(patch).eq("id", operational_run_id).execute()


def insert_operational_failure(
    client: Client,
    *,
    operational_run_id: str,
    failure_category: str,
    detail: str,
) -> None:
    client.table("operational_failures").insert(
        {
            "operational_run_id": operational_run_id,
            "failure_category": failure_category,
            "detail": detail[:8000],
        }
    ).execute()


def fetch_operational_runs_recent(
    client: Client, *, limit: int = 100
) -> list[dict[str, Any]]:
    r = (
        client.table("operational_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_operational_failures_recent(
    client: Client, *, limit: int = 100
) -> list[dict[str, Any]]:
    r = (
        client.table("operational_failures")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_operational_run(
    client: Client, *, operational_run_id: str
) -> Optional[dict[str, Any]]:
    res = (
        client.table("operational_runs")
        .select("*")
        .eq("id", operational_run_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return dict(res.data[0])


def insert_research_hypothesis(
    client: Client,
    *,
    title: str,
    research_item_status: str,
    source_scope: str,
    intended_use: str,
    leakage_review_status: str = "not_reviewed",
    promotion_decision: str = "none",
    rejection_reason: Optional[str] = None,
    linked_artifacts: Optional[list[Any]] = None,
    notes_json: Optional[dict[str, Any]] = None,
) -> str:
    row: dict[str, Any] = {
        "title": title[:2000],
        "research_item_status": research_item_status,
        "source_scope": source_scope[:2000],
        "intended_use": intended_use[:4000],
        "leakage_review_status": leakage_review_status,
        "promotion_decision": promotion_decision,
        "rejection_reason": rejection_reason,
        "linked_artifacts": linked_artifacts or [],
        "notes_json": notes_json or {},
        "stub_status": "active",
    }
    res = client.table("hypothesis_registry").insert(row).execute()
    if not res.data:
        raise RuntimeError("hypothesis_registry insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_research_hypotheses(
    client: Client, *, limit: int = 200
) -> list[dict[str, Any]]:
    r = (
        client.table("hypothesis_registry")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def insert_promotion_gate_event(
    client: Client,
    *,
    hypothesis_id: Optional[str],
    event_type: str,
    decision_summary: Optional[str],
    rationale: Optional[str],
    actor: Optional[str],
    metadata_json: Optional[dict[str, Any]] = None,
) -> str:
    row: dict[str, Any] = {
        "hypothesis_id": hypothesis_id,
        "event_type": event_type,
        "decision_summary": decision_summary,
        "rationale": rationale,
        "actor": actor,
        "metadata_json": metadata_json or {},
        "stub_status": "recorded",
    }
    res = client.table("promotion_gate_events").insert(row).execute()
    if not res.data:
        raise RuntimeError("promotion_gate_events insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_promotion_gate_events_recent(
    client: Client, *, limit: int = 100
) -> list[dict[str, Any]]:
    r = (
        client.table("promotion_gate_events")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def hypothesis_exists_by_title(client: Client, *, title: str) -> bool:
    r = (
        client.table("hypothesis_registry")
        .select("id")
        .eq("title", title)
        .limit(1)
        .execute()
    )
    return bool(r.data)


# --- Phase 10: source registry & overlays ---


def smoke_source_registry_tables(client: Client) -> None:
    client.table("data_source_registry").select("source_id").limit(1).execute()
    client.table("source_overlay_availability").select("overlay_key").limit(1).execute()
    try:
        client.table("raw_transcript_payloads_fmp_history").select("id").limit(1).execute()
    except Exception:
        pass


def fetch_data_source_registry_all(client: Client) -> list[dict[str, Any]]:
    r = (
        client.table("data_source_registry")
        .select("*")
        .order("source_id")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_source_overlay_availability_all(client: Client) -> list[dict[str, Any]]:
    r = (
        client.table("source_overlay_availability")
        .select("*")
        .order("overlay_key")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_source_access_profiles_for_source(
    client: Client, *, source_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("source_access_profiles")
        .select("*")
        .eq("source_id", source_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def upsert_data_source_registry_row(client: Client, row: dict[str, Any]) -> None:
    client.table("data_source_registry").upsert(row, on_conflict="source_id").execute()


def insert_source_overlay_gap_report(
    client: Client, *, payload_json: dict[str, Any], report_type: str = "roi_gap_v1"
) -> str:
    res = (
        client.table("source_overlay_gap_reports")
        .insert({"report_type": report_type, "payload_json": payload_json})
        .execute()
    )
    if not res.data:
        raise RuntimeError("source_overlay_gap_reports insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


# --- Phase 11: FMP transcript PoC (single vendor) ---


def fetch_source_overlay_availability_by_key(
    client: Client, *, overlay_key: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("source_overlay_availability")
        .select("*")
        .eq("overlay_key", overlay_key)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def merge_update_source_overlay_availability(
    client: Client,
    *,
    overlay_key: str,
    availability: Optional[str],
    metadata_patch: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    row = fetch_source_overlay_availability_by_key(client, overlay_key=overlay_key)
    base_meta: dict[str, Any] = {}
    if row and isinstance(row.get("metadata_json"), dict):
        base_meta = dict(row["metadata_json"])
    merged = {**base_meta, **metadata_patch, "phase11_last_touch_utc": now}
    upd: dict[str, Any] = {
        "last_checked_at": now,
        "metadata_json": merged,
        "updated_at": now,
    }
    if availability is not None:
        upd["availability"] = availability
    client.table("source_overlay_availability").update(upd).eq("overlay_key", overlay_key).execute()


def insert_transcript_ingest_run(
    client: Client,
    *,
    provider_code: str,
    operation: str,
    status: str,
    probe_status: Optional[str] = None,
    detail_json: Optional[dict[str, Any]] = None,
) -> str:
    row = {
        "provider_code": provider_code,
        "operation": operation,
        "probe_status": probe_status,
        "status": status,
        "detail_json": detail_json or {},
    }
    res = client.table("transcript_ingest_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("transcript_ingest_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def insert_source_overlay_run_row(
    client: Client,
    *,
    run_type: str,
    status: str = "completed",
    payload_json: dict[str, Any],
) -> str:
    res = (
        client.table("source_overlay_runs")
        .insert({"run_type": run_type, "status": status, "payload_json": payload_json})
        .execute()
    )
    if not res.data:
        raise RuntimeError("source_overlay_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def patch_data_source_registry_activation(
    client: Client, *, source_id: str, activation_status: str
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    client.table("data_source_registry").update(
        {"activation_status": activation_status, "updated_at": now}
    ).eq("source_id", source_id).execute()


def fetch_raw_transcript_payload_fmp(
    client: Client,
    *,
    symbol: str,
    fiscal_year: int,
    fiscal_quarter: int,
) -> Optional[dict[str, Any]]:
    r = (
        client.table("raw_transcript_payloads_fmp")
        .select("*")
        .eq("symbol", symbol.upper().strip())
        .eq("fiscal_year", int(fiscal_year))
        .eq("fiscal_quarter", int(fiscal_quarter))
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_raw_transcript_payload_fmp_history(
    client: Client,
    *,
    symbol: str,
    fiscal_year: int,
    fiscal_quarter: int,
    http_status: Optional[int],
    raw_response_json: Any,
    superseded_raw_payload_id: Optional[str],
    ingest_run_id: Optional[str],
) -> str:
    row = {
        "symbol": symbol.upper().strip(),
        "fiscal_year": int(fiscal_year),
        "fiscal_quarter": int(fiscal_quarter),
        "http_status": http_status,
        "raw_response_json": raw_response_json,
        "superseded_raw_payload_id": superseded_raw_payload_id,
        "ingest_run_id": ingest_run_id,
    }
    res = client.table("raw_transcript_payloads_fmp_history").insert(row).execute()
    if not res.data:
        raise RuntimeError("raw_transcript_payloads_fmp_history insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def archive_raw_transcript_payload_fmp_before_upsert(
    client: Client,
    *,
    symbol: str,
    fiscal_year: int,
    fiscal_quarter: int,
    ingest_run_id: Optional[str],
) -> Optional[str]:
    """
    If a latest raw row exists, copy it to history before upsert (audit trail).
    Returns new history row id or None.
    """
    ex = fetch_raw_transcript_payload_fmp(
        client,
        symbol=symbol,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
    )
    if not ex:
        return None
    rid = ex.get("id")
    return insert_raw_transcript_payload_fmp_history(
        client,
        symbol=symbol,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        http_status=ex.get("http_status"),
        raw_response_json=ex.get("raw_response_json") or {},
        superseded_raw_payload_id=str(rid) if rid is not None else None,
        ingest_run_id=ingest_run_id,
    )


def upsert_raw_transcript_payload_fmp(
    client: Client,
    *,
    symbol: str,
    fiscal_year: int,
    fiscal_quarter: int,
    http_status: Optional[int],
    raw_response_json: Any,
    ingest_run_id: Optional[str] = None,
) -> str:
    row = {
        "symbol": symbol.upper().strip(),
        "fiscal_year": int(fiscal_year),
        "fiscal_quarter": int(fiscal_quarter),
        "http_status": http_status,
        "raw_response_json": raw_response_json,
        "ingest_run_id": ingest_run_id,
    }
    res = (
        client.table("raw_transcript_payloads_fmp")
        .upsert(row, on_conflict="symbol,fiscal_year,fiscal_quarter")
        .select("id")
        .execute()
    )
    if not res.data:
        raise RuntimeError("raw_transcript_payloads_fmp upsert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def upsert_normalized_transcript(client: Client, row: dict[str, Any]) -> str:
    res = (
        client.table("normalized_transcripts")
        .upsert(row, on_conflict="provider_name,ticker,fiscal_period")
        .select("id")
        .execute()
    )
    if not res.data:
        raise RuntimeError("normalized_transcripts upsert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_latest_normalized_transcript_for_ticker(
    client: Client, *, ticker: str, provider_name: str = "financial_modeling_prep"
) -> Optional[dict[str, Any]]:
    r = (
        client.table("normalized_transcripts")
        .select("*")
        .eq("ticker", ticker.upper().strip())
        .eq("provider_name", provider_name)
        .order("ingested_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_normalized_transcripts_for_ticker_recent(
    client: Client,
    *,
    ticker: str,
    provider_name: str = "financial_modeling_prep",
    limit: int = 200,
) -> list[dict[str, Any]]:
    r = (
        client.table("normalized_transcripts")
        .select("*")
        .eq("ticker", ticker.upper().strip())
        .eq("provider_name", provider_name)
        .order("ingested_at", desc=True)
        .limit(int(limit))
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_normalized_transcript_by_period(
    client: Client,
    *,
    provider_name: str,
    ticker: str,
    fiscal_period: str,
) -> Optional[dict[str, Any]]:
    r = (
        client.table("normalized_transcripts")
        .select("*")
        .eq("provider_name", provider_name)
        .eq("ticker", ticker.upper().strip())
        .eq("fiscal_period", fiscal_period)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_issuer_id_for_ticker(client: Client, *, ticker: str) -> Optional[str]:
    r = (
        client.table("issuer_master")
        .select("id")
        .eq("ticker", ticker.upper().strip())
        .limit(1)
        .execute()
    )
    if not r.data or not r.data[0].get("id"):
        return None
    return str(r.data[0]["id"])


# --- Phase 14 research engine kernel ---


def smoke_phase14_research_engine_tables(client: Client) -> None:
    client.table("research_programs").select("id").limit(1).execute()


def fetch_public_core_cycle_quality_run_by_id(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_core_cycle_quality_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_research_program(client: Client, row: dict[str, Any]) -> str:
    res = client.table("research_programs").insert(row).execute()
    if not res.data:
        raise RuntimeError("research_programs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_research_program(client: Client, *, program_id: str) -> Optional[dict[str, Any]]:
    r = (
        client.table("research_programs")
        .select("*")
        .eq("id", program_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_research_programs_recent(client: Client, *, limit: int = 50) -> list[dict[str, Any]]:
    r = (
        client.table("research_programs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def list_research_programs_for_universe(
    client: Client, *, universe_name: str, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("research_programs")
        .select("*")
        .eq("universe_name", universe_name)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def insert_research_hypothesis_object(client: Client, row: dict[str, Any]) -> str:
    res = client.table("research_hypotheses").insert(row).execute()
    if not res.data:
        raise RuntimeError("research_hypotheses insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_research_hypothesis(
    client: Client, *, hypothesis_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("research_hypotheses")
        .select("*")
        .eq("id", hypothesis_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_research_hypotheses_for_program(
    client: Client, *, program_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("research_hypotheses")
        .select("*")
        .eq("program_id", program_id)
        .order("created_at")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def update_research_hypothesis(
    client: Client, hypothesis_id: str, patch: dict[str, Any]
) -> None:
    client.table("research_hypotheses").update(patch).eq("id", hypothesis_id).execute()


def insert_research_reviews_batch(client: Client, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    step = 20
    for i in range(0, len(rows), step):
        client.table("research_reviews").insert(rows[i : i + step]).execute()


def fetch_research_reviews_for_hypothesis(
    client: Client, *, hypothesis_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("research_reviews")
        .select("*")
        .eq("hypothesis_id", hypothesis_id)
        .order("round_number")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_research_reviews_for_program(
    client: Client, *, program_id: str
) -> list[dict[str, Any]]:
    hyps = fetch_research_hypotheses_for_program(client, program_id=program_id)
    if not hyps:
        return []
    ids = [str(h["id"]) for h in hyps]
    r = (
        client.table("research_reviews")
        .select("*")
        .in_("hypothesis_id", ids)
        .order("hypothesis_id")
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def insert_research_referee_decision(client: Client, row: dict[str, Any]) -> str:
    res = client.table("research_referee_decisions").insert(row).execute()
    if not res.data:
        raise RuntimeError("research_referee_decisions insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_research_referee_decisions_for_hypothesis(
    client: Client, *, hypothesis_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("research_referee_decisions")
        .select("*")
        .eq("hypothesis_id", hypothesis_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_research_referee_for_program(
    client: Client, *, program_id: str
) -> list[dict[str, Any]]:
    hyps = fetch_research_hypotheses_for_program(client, program_id=program_id)
    out: list[dict[str, Any]] = []
    for h in hyps:
        rows = fetch_research_referee_decisions_for_hypothesis(
            client, hypothesis_id=str(h["id"])
        )
        if rows:
            out.append(rows[0])
    return out


def insert_research_residual_link(client: Client, row: dict[str, Any]) -> str:
    res = client.table("research_residual_links").insert(row).execute()
    if not res.data:
        raise RuntimeError("research_residual_links insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_research_residual_links_for_hypothesis(
    client: Client, *, hypothesis_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("research_residual_links")
        .select("*")
        .eq("hypothesis_id", hypothesis_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_research_residual_links_for_program(
    client: Client, *, program_id: str
) -> list[dict[str, Any]]:
    hyps = fetch_research_hypotheses_for_program(client, program_id=program_id)
    out: list[dict[str, Any]] = []
    for h in hyps:
        out.extend(
            fetch_research_residual_links_for_hypothesis(
                client, hypothesis_id=str(h["id"])
            )
        )
    return out


# --- Phase 15 recipe validation lab ---


def smoke_phase15_recipe_validation_tables(client: Client) -> None:
    client.table("recipe_validation_runs").select("id").limit(1).execute()


def insert_recipe_validation_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("recipe_validation_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("recipe_validation_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_recipe_validation_run(
    client: Client, *, run_id: str, patch: dict[str, Any]
) -> None:
    client.table("recipe_validation_runs").update(patch).eq("id", run_id).execute()


def fetch_recipe_validation_run(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("recipe_validation_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_latest_recipe_validation_run_for_hypothesis(
    client: Client, *, hypothesis_id: str, status: Optional[str] = "completed"
) -> Optional[dict[str, Any]]:
    q = client.table("recipe_validation_runs").select("*").eq("hypothesis_id", hypothesis_id)
    if status is not None:
        q = q.eq("status", status)
    r = q.order("created_at", desc=True).limit(1).execute()
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_recipe_validation_results_for_run(
    client: Client, *, validation_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("recipe_validation_results")
        .select("*")
        .eq("validation_run_id", validation_run_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_recipe_validation_comparisons_for_run(
    client: Client, *, validation_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("recipe_validation_comparisons")
        .select("*")
        .eq("validation_run_id", validation_run_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_recipe_survival_for_run(
    client: Client, *, validation_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("recipe_survival_decisions")
        .select("*")
        .eq("validation_run_id", validation_run_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_recipe_failure_cases_for_run(
    client: Client, *, validation_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("recipe_failure_cases")
        .select("*")
        .eq("validation_run_id", validation_run_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_recipe_survivors_recent(
    client: Client, *, limit: int = 50
) -> list[dict[str, Any]]:
    r = (
        client.table("recipe_survival_decisions")
        .select("*")
        .in_("survival_status", ["survives", "weak_survival"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def insert_recipe_validation_results_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 50
    for i in range(0, len(rows), step):
        client.table("recipe_validation_results").insert(rows[i : i + step]).execute()


def insert_recipe_validation_comparisons_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 30
    for i in range(0, len(rows), step):
        client.table("recipe_validation_comparisons").insert(rows[i : i + step]).execute()


def insert_recipe_survival_decision(client: Client, row: dict[str, Any]) -> str:
    res = client.table("recipe_survival_decisions").insert(row).execute()
    if not res.data:
        raise RuntimeError("recipe_survival_decisions insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def insert_recipe_failure_cases_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 30
    for i in range(0, len(rows), step):
        client.table("recipe_failure_cases").insert(rows[i : i + step]).execute()


# --- Phase 16 validation campaign ---


def smoke_phase16_validation_campaign_tables(client: Client) -> None:
    client.table("validation_campaign_runs").select("id").limit(1).execute()


def insert_validation_campaign_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("validation_campaign_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("validation_campaign_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_validation_campaign_run(
    client: Client, *, campaign_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("validation_campaign_runs")
        .select("*")
        .eq("id", campaign_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_validation_campaign_members_batch(
    client: Client, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    step = 30
    for i in range(0, len(rows), step):
        client.table("validation_campaign_members").insert(rows[i : i + step]).execute()


def fetch_validation_campaign_members(
    client: Client, *, campaign_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("validation_campaign_members")
        .select("*")
        .eq("campaign_run_id", campaign_run_id)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def insert_validation_campaign_decision(client: Client, row: dict[str, Any]) -> str:
    res = client.table("validation_campaign_decisions").insert(row).execute()
    if not res.data:
        raise RuntimeError("validation_campaign_decisions insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_validation_campaign_decisions(
    client: Client, *, campaign_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("validation_campaign_decisions")
        .select("*")
        .eq("campaign_run_id", campaign_run_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


# --- Phase 17 public substrate depth ---


def smoke_phase17_public_depth_tables(client: Client) -> None:
    client.table("public_depth_runs").select("id").limit(1).execute()


def insert_public_depth_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_depth_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_depth_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_public_depth_run(client: Client, *, run_id: str, patch: dict[str, Any]) -> None:
    client.table("public_depth_runs").update(patch).eq("id", run_id).execute()


def fetch_public_depth_run(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_depth_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_public_depth_coverage_report(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_depth_coverage_reports").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_depth_coverage_reports insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_public_depth_coverage_report(
    client: Client, *, report_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_depth_coverage_reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_public_depth_coverage_reports_for_universe(
    client: Client, *, universe_name: str, limit: int = 2
) -> list[dict[str, Any]]:
    """`created_at` 내림차순(최신이 먼저)."""
    r = (
        client.table("public_depth_coverage_reports")
        .select("*")
        .eq("universe_name", universe_name)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    if not r.data:
        return []
    return [dict(row) for row in r.data]


def insert_public_depth_uplift_report(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_depth_uplift_reports").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_depth_uplift_reports insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


# --- Phase 18 targeted public build-out ---


def smoke_phase18_public_buildout_tables(client: Client) -> None:
    client.table("public_exclusion_action_reports").select("id").limit(1).execute()
    client.table("public_buildout_runs").select("id").limit(1).execute()
    client.table("public_buildout_improvement_reports").select("id").limit(1).execute()


def insert_public_exclusion_action_report(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_exclusion_action_reports").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_exclusion_action_reports insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def insert_public_buildout_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_buildout_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_buildout_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_public_buildout_run(
    client: Client, *, run_id: str, patch: dict[str, Any]
) -> None:
    client.table("public_buildout_runs").update(patch).eq("id", run_id).execute()


def fetch_public_buildout_run(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_buildout_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_public_buildout_improvement_report(
    client: Client, row: dict[str, Any]
) -> str:
    res = client.table("public_buildout_improvement_reports").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_buildout_improvement_reports insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


# --- Phase 19 public repair campaign ---


def smoke_phase19_public_repair_campaign_tables(client: Client) -> None:
    client.table("public_repair_campaign_runs").select("id").limit(1).execute()
    client.table("public_repair_campaign_steps").select("id").limit(1).execute()
    client.table("public_repair_revalidation_comparisons").select("id").limit(1).execute()
    client.table("public_repair_campaign_decisions").select("id").limit(1).execute()


def insert_public_repair_campaign_run(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_campaign_runs").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_campaign_runs insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_public_repair_campaign_run(
    client: Client, *, run_id: str, patch: dict[str, Any]
) -> None:
    client.table("public_repair_campaign_runs").update(patch).eq("id", run_id).execute()


def fetch_public_repair_campaign_run(
    client: Client, *, run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_repair_campaign_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_public_repair_campaign_runs_for_program(
    client: Client, *, program_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_campaign_runs")
        .select("*")
        .eq("program_id", program_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(row) for row in (r.data or [])]


def insert_public_repair_campaign_step(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_campaign_steps").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_campaign_steps insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_public_repair_campaign_steps(
    client: Client, *, repair_campaign_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_campaign_steps")
        .select("*")
        .eq("repair_campaign_run_id", repair_campaign_run_id)
        .order("created_at", desc=False)
        .execute()
    )
    return [dict(row) for row in (r.data or [])]


def insert_public_repair_revalidation_comparison(
    client: Client, row: dict[str, Any]
) -> str:
    res = client.table("public_repair_revalidation_comparisons").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_revalidation_comparisons insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_public_repair_revalidation_comparison_for_run(
    client: Client, *, repair_campaign_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_repair_revalidation_comparisons")
        .select("*")
        .eq("repair_campaign_run_id", repair_campaign_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def upsert_public_repair_revalidation_comparison(
    client: Client, row: dict[str, Any]
) -> str:
    """단일 비교 행(유니크 repair_campaign_run_id). 기존 행이 있으면 삭제 후 삽입."""
    rid = str(row["repair_campaign_run_id"])
    existing = fetch_public_repair_revalidation_comparison_for_run(
        client, repair_campaign_run_id=rid
    )
    if existing:
        client.table("public_repair_revalidation_comparisons").delete().eq(
            "repair_campaign_run_id", rid
        ).execute()
    return insert_public_repair_revalidation_comparison(client, row)


def insert_public_repair_campaign_decision(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_campaign_decisions").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_campaign_decisions insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def fetch_public_repair_campaign_decisions(
    client: Client, *, repair_campaign_run_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_campaign_decisions")
        .select("*")
        .eq("repair_campaign_run_id", repair_campaign_run_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [dict(row) for row in (r.data or [])]


def fetch_latest_validation_campaign_run_for_program(
    client: Client, *, program_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("validation_campaign_runs")
        .select("*")
        .eq("program_id", program_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


# --- Phase 20 repair iteration / escalation ---


def smoke_phase20_repair_iteration_tables(client: Client) -> None:
    client.table("public_repair_iteration_series").select("id").limit(1).execute()
    client.table("public_repair_iteration_members").select("id").limit(1).execute()
    client.table("public_repair_escalation_decisions").select("id").limit(1).execute()


def smoke_phase21_iteration_governance(client: Client) -> None:
    smoke_phase20_repair_iteration_tables(client)
    client.table("public_repair_iteration_series").select("governance_audit_json").limit(1).execute()


def smoke_phase22_public_depth_iteration_members(client: Client) -> None:
    """Phase 22: iteration members may link public_depth_runs."""
    smoke_phase21_iteration_governance(client)
    client.table("public_repair_iteration_members").select(
        "member_kind,public_depth_run_id"
    ).limit(1).execute()


def insert_public_repair_iteration_series(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_iteration_series").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_iteration_series insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def update_public_repair_iteration_series(
    client: Client, *, series_id: str, patch: dict[str, Any]
) -> None:
    client.table("public_repair_iteration_series").update(patch).eq("id", series_id).execute()


def fetch_public_repair_iteration_series(
    client: Client, *, series_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_series")
        .select("*")
        .eq("id", series_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_active_public_repair_iteration_series_for_program(
    client: Client, *, program_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_series")
        .select("*")
        .eq("program_id", program_id)
        .eq("status", "active")
        .order("updated_at", desc=True)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def list_public_repair_iteration_series_for_program(
    client: Client, *, program_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_series")
        .select("*")
        .eq("program_id", program_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def list_open_public_repair_iteration_series_for_triple(
    client: Client,
    *,
    program_id: str,
    universe_name: str,
    policy_version: str,
) -> list[dict[str, Any]]:
    """Active or paused rows for (program, universe, policy); at most one after Phase 21 index."""
    r = (
        client.table("public_repair_iteration_series")
        .select("*")
        .eq("program_id", program_id)
        .eq("universe_name", universe_name)
        .eq("policy_version", policy_version)
        .in_("status", ["active", "paused"])
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_public_repair_iteration_member_by_run_id(
    client: Client, *, repair_campaign_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_members")
        .select("*")
        .eq("repair_campaign_run_id", repair_campaign_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def fetch_public_repair_iteration_member_by_depth_run_id(
    client: Client, *, public_depth_run_id: str
) -> Optional[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_members")
        .select("*")
        .eq("public_depth_run_id", public_depth_run_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def insert_public_repair_iteration_member(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_iteration_members").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_iteration_members insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def list_public_repair_iteration_members_for_series(
    client: Client, *, series_id: str
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_iteration_members")
        .select("*")
        .eq("series_id", series_id)
        .order("sequence_number", desc=False)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]


def fetch_max_sequence_public_repair_iteration_member(
    client: Client, *, series_id: str
) -> int:
    r = (
        client.table("public_repair_iteration_members")
        .select("sequence_number")
        .eq("series_id", series_id)
        .order("sequence_number", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return 0
    return int(r.data[0]["sequence_number"])


def insert_public_repair_escalation_decision(client: Client, row: dict[str, Any]) -> str:
    res = client.table("public_repair_escalation_decisions").insert(row).execute()
    if not res.data:
        raise RuntimeError("public_repair_escalation_decisions insert 응답이 비어 있습니다.")
    return str(res.data[0]["id"])


def list_public_repair_escalation_decisions_for_series(
    client: Client, *, series_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    r = (
        client.table("public_repair_escalation_decisions")
        .select("*")
        .eq("series_id", series_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [dict(x) for x in (r.data or [])]
