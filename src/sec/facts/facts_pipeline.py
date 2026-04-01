"""
XBRL facts 적재 파이프라인: raw → silver → issuer_quarter_snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sec.facts.build_quarter_snapshot import build_snapshot_row
from sec.facts.extract_facts import extract_facts_for_ticker
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
    """
    ext = extract_facts_for_ticker(
        ticker, settings.edgar_identity, forms=forms
    )
    if not ext.get("ok"):
        return ext

    cik = ext["cik"]
    accession_no = ext["accession_no"]
    raw_rows: list[dict[str, Any]] = ext["raw_rows"]
    filed_at = _parse_iso_dt(ext.get("filed_at"))
    accepted_at = _parse_iso_dt(ext.get("accepted_at"))

    raw_inserted = 0
    raw_skipped = 0
    silver_inserted = 0
    silver_skipped = 0

    from db.records import (
        insert_raw_xbrl_fact,
        insert_silver_xbrl_fact,
        raw_xbrl_fact_exists,
        silver_xbrl_fact_exists,
        upsert_issuer_quarter_snapshot,
    )

    for raw in raw_rows:
        if raw_xbrl_fact_exists(
            client,
            cik=cik,
            accession_no=accession_no,
            dedupe_key=raw["dedupe_key"],
        ):
            raw_skipped += 1
        else:
            insert_raw_xbrl_fact(client, raw)
            raw_inserted += 1

        silver = raw_dict_to_silver_candidate(raw, revision_no=revision_no)
        if not silver:
            continue
        if silver_xbrl_fact_exists(
            client,
            cik=cik,
            accession_no=accession_no,
            canonical_concept=silver["canonical_concept"],
            revision_no=revision_no,
            fact_period_key=silver["fact_period_key"],
        ):
            silver_skipped += 1
        else:
            insert_silver_xbrl_fact(client, silver)
            silver_inserted += 1

    silver_for_snap: list[dict[str, Any]] = []
    for raw in raw_rows:
        s = raw_dict_to_silver_candidate(raw, revision_no=revision_no)
        if s:
            silver_for_snap.append(s)

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
        "ticker": ext["ticker"],
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
