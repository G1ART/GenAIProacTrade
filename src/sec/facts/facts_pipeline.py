"""
XBRL facts 적재 파이프라인: raw → silver → issuer_quarter_snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sec.facts.build_quarter_snapshot import build_snapshot_row
from sec.facts.extract_facts import extract_facts_for_ticker, extract_facts_for_ticker_multi
from sec.facts.normalize_facts import raw_dict_to_silver_candidate
from sec.normalize import parse_accepted_at, parse_filed_at
from sec.validation.arelle_check import compare_statement_concept_presence, validate_xbrl_fact_presence


def _parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _ingest_single_filing_payload(
    client: Any,
    ext: dict[str, Any],
    *,
    revision_no: int,
    run_validation_hook: bool,
) -> dict[str, Any]:
    """
    단일 filing 추출 payload를 raw/silver/snapshot으로 적재한다.

    ``ext`` 는 extract_facts_for_ticker 또는 extract_facts_for_ticker_multi의
    각 filing 요소와 동일한 형태:
        {ok, ticker, cik, accession_no, form, raw_rows, filed_at, accepted_at, ...}
    """
    if not ext.get("ok"):
        return ext

    cik = ext["cik"]
    accession_no = ext["accession_no"]
    raw_rows: list[dict[str, Any]] = ext.get("raw_rows") or []
    filed_at = _parse_iso_dt(ext.get("filed_at"))
    accepted_at = _parse_iso_dt(ext.get("accepted_at"))

    raw_skipped = 0
    silver_skipped = 0

    from db.records import (
        fetch_raw_xbrl_fact_dedupe_keys_for_filing,
        fetch_silver_xbrl_fact_keys_for_filing,
        insert_raw_xbrl_facts_bulk,
        insert_silver_xbrl_facts_bulk,
        upsert_issuer_quarter_snapshot,
    )

    existing_raw_keys = fetch_raw_xbrl_fact_dedupe_keys_for_filing(
        client, cik=cik, accession_no=accession_no
    )
    new_raw_rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        dk = str(raw.get("dedupe_key") or "")
        if not dk or dk in existing_raw_keys:
            raw_skipped += 1
            continue
        existing_raw_keys.add(dk)
        new_raw_rows.append(raw)
    raw_inserted = insert_raw_xbrl_facts_bulk(client, new_raw_rows)

    silver_for_snap: list[dict[str, Any]] = []
    for raw in raw_rows:
        s = raw_dict_to_silver_candidate(raw, revision_no=revision_no)
        if s:
            silver_for_snap.append(s)

    existing_silver_keys = fetch_silver_xbrl_fact_keys_for_filing(
        client, cik=cik, accession_no=accession_no
    )
    new_silver_rows: list[dict[str, Any]] = []
    for silver in silver_for_snap:
        try:
            sk = (
                str(silver.get("canonical_concept") or ""),
                int(revision_no),
                str(silver.get("fact_period_key") or ""),
            )
        except (TypeError, ValueError):
            silver_skipped += 1
            continue
        if sk in existing_silver_keys:
            silver_skipped += 1
            continue
        existing_silver_keys.add(sk)
        new_silver_rows.append(silver)
    silver_inserted = insert_silver_xbrl_facts_bulk(client, new_silver_rows)

    snap_row = build_snapshot_row(
        raw_rows=raw_rows,
        silver_rows=silver_for_snap,
        cik=cik,
        accession_no=accession_no,
        filed_at=filed_at,
        accepted_at=accepted_at,
    )
    snap_result = upsert_issuer_quarter_snapshot(client, snap_row)

    validation: dict[str, Any] = {}
    if run_validation_hook:
        validation["xbrl_fact_presence"] = validate_xbrl_fact_presence(
            cik=cik,
            accession_no=accession_no,
            source_fact_count=len(raw_rows),
            mapped_silver_count=len(silver_for_snap),
        )
        validation["statement_concept_presence"] = compare_statement_concept_presence(
            cik=cik,
            accession_no=accession_no,
            canonical_present=sorted(
                {s["canonical_concept"] for s in silver_for_snap}
            ),
        )

    return {
        "ok": True,
        "ticker": ext.get("ticker"),
        "cik": cik,
        "accession_no": accession_no,
        "form": ext.get("form"),
        "raw_fact_count": len(raw_rows),
        "raw_inserted": raw_inserted,
        "raw_skipped": raw_skipped,
        "silver_inserted": silver_inserted,
        "silver_skipped": silver_skipped,
        "snapshot": snap_result,
        "arelle_validation": validation,
    }


def run_facts_extract_for_ticker(
    client: Any,
    settings: Any,
    ticker: str,
    *,
    revision_no: int = 1,
    forms: tuple[str, ...] = ("10-Q", "10-K"),
    run_validation_hook: bool = True,
) -> dict[str, Any]:
    """
    EdgarTools로 XBRL 공시를 찾고 raw_xbrl_facts / silver_xbrl_facts / issuer_quarter_snapshots 적재.

    티커당 **1건**의 최신 XBRL 공시만 처리한다. 복수 분기 백필이 필요하면
    ``run_facts_extract_for_ticker_multi`` 를 사용한다.
    """
    ext = extract_facts_for_ticker(
        ticker, settings.edgar_identity, forms=forms
    )
    if not ext.get("ok"):
        return ext
    return _ingest_single_filing_payload(
        client, ext, revision_no=revision_no, run_validation_hook=run_validation_hook
    )


def run_facts_extract_for_ticker_multi(
    client: Any,
    settings: Any,
    ticker: str,
    *,
    limit: int = 1,
    revision_no: int = 1,
    forms: tuple[str, ...] = ("10-Q", "10-K"),
    run_validation_hook: bool = True,
) -> dict[str, Any]:
    """
    티커당 최대 ``limit`` 건의 최근 XBRL 공시에 대해 raw/silver/snapshot 적재.

    prior-quarter 의존 팩터(accruals 등) 계산을 위해 CIK당 복수 분기 스냅샷을
    확보하는 것이 이 함수의 주목적이다.
    """
    tnorm = ticker.upper().strip()
    ext = extract_facts_for_ticker_multi(
        ticker, settings.edgar_identity, forms=forms, limit=limit
    )
    filings: list[dict[str, Any]] = ext.get("filings") or []

    if not ext.get("ok") and not filings:
        return {
            "ok": False,
            "ticker": tnorm,
            "requested_limit": int(limit),
            "filings_ingested": 0,
            "filings_failed": 0,
            "results": [],
            "errors": [{k: v for k, v in ext.items() if k != "filings"}],
        }

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ingested = 0
    failed = 0

    agg = {
        "raw_fact_count": 0,
        "raw_inserted": 0,
        "raw_skipped": 0,
        "silver_inserted": 0,
        "silver_skipped": 0,
    }

    for payload in filings:
        if not payload.get("ok"):
            failed += 1
            errors.append(
                {
                    "accession_no": payload.get("accession_no"),
                    **{k: v for k, v in payload.items() if k not in ("raw_rows", "ok")},
                }
            )
            continue
        try:
            out = _ingest_single_filing_payload(
                client,
                payload,
                revision_no=revision_no,
                run_validation_hook=run_validation_hook,
            )
        except Exception as ex:  # noqa: BLE001
            failed += 1
            errors.append(
                {
                    "accession_no": payload.get("accession_no"),
                    "error": "ingest_failed",
                    "detail": str(ex),
                }
            )
            continue
        if out.get("ok"):
            ingested += 1
            for k in agg:
                agg[k] += int(out.get(k) or 0)
            results.append(
                {k: v for k, v in out.items() if k != "arelle_validation"}
            )
        else:
            failed += 1
            errors.append(
                {k: v for k, v in out.items() if k != "ok"}
            )

    return {
        "ok": ingested > 0,
        "ticker": tnorm,
        "requested_limit": int(limit),
        "filings_ingested": ingested,
        "filings_failed": failed,
        "raw_fact_count_total": agg["raw_fact_count"],
        "raw_inserted_total": agg["raw_inserted"],
        "raw_skipped_total": agg["raw_skipped"],
        "silver_inserted_total": agg["silver_inserted"],
        "silver_skipped_total": agg["silver_skipped"],
        "results": results,
        "errors": errors,
    }


def rebuild_quarter_snapshot_from_db(
    client: Any,
    *,
    cik: str,
    accession_no: str,
) -> dict[str, Any]:
    """DB에 적재된 raw/silver로 스냅샷만 재계산·upsert."""
    from db.records import (
        fetch_raw_xbrl_facts_for_filing,
        fetch_silver_xbrl_facts_for_filing,
        upsert_issuer_quarter_snapshot,
    )

    raw_rows = fetch_raw_xbrl_facts_for_filing(client, cik=cik, accession_no=accession_no)
    silver_rows = fetch_silver_xbrl_facts_for_filing(client, cik=cik, accession_no=accession_no)
    if not silver_rows:
        return {"ok": False, "error": "no_silver_facts", "cik": cik, "accession_no": accession_no}

    filed_at = None
    accepted_at = None
    if raw_rows:
        filed_at = _parse_iso_dt(str(raw_rows[0].get("filed_at") or ""))
        accepted_at = parse_accepted_at(raw_rows[0].get("accepted_at"))
        if not filed_at and raw_rows[0].get("filed_at"):
            filed_at = parse_filed_at(str(raw_rows[0]["filed_at"])[:10])

    snap_row = build_snapshot_row(
        raw_rows=raw_rows,
        silver_rows=silver_rows,
        cik=cik,
        accession_no=accession_no,
        filed_at=filed_at,
        accepted_at=accepted_at,
    )
    snap_result = upsert_issuer_quarter_snapshot(client, snap_row)
    return {
        "ok": True,
        "cik": cik,
        "accession_no": accession_no,
        "snapshot": snap_result,
    }
