"""
silver / raw 후보에서 issuer_quarter_snapshots 행 조립.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sec.facts.normalize_facts import parse_primary_fiscal_from_facts

CANONICAL_TO_SNAPSHOT_COL = {
    "revenue": "revenue",
    "net_income": "net_income",
    "operating_cash_flow": "operating_cash_flow",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "cash_and_equivalents": "cash_and_equivalents",
    "research_and_development": "research_and_development",
    "capex": "capex",
    "gross_profit": "gross_profit",
    "shares_outstanding": "shares_outstanding",
}

_INSTANT_CANONICALS = frozenset(
    {
        "total_assets",
        "total_liabilities",
        "cash_and_equivalents",
        "shares_outstanding",
    }
)


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _coerce_period_dates(
    silver_rows: list[dict[str, Any]],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """duration fact의 period_start/end를 스냅샷에 반영."""
    ps: Optional[date] = None
    pe: Optional[date] = None
    for s in silver_rows:
        if s.get("fact_type") != "duration":
            continue
        a = _parse_date(s.get("period_start"))
        b = _parse_date(s.get("period_end"))
        if a and (ps is None or a < ps):
            ps = a
        if b and (pe is None or b > pe):
            pe = b
    def to_utc_dt(d: Optional[date]) -> Optional[datetime]:
        if d is None:
            return None
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    return to_utc_dt(ps), to_utc_dt(pe)


def _fallback_primary_fiscal(silver_mapped: list[dict[str, Any]]) -> tuple[Optional[int], Optional[str]]:
    cands = [
        s
        for s in silver_mapped
        if s.get("canonical_concept") == "revenue" and s.get("fiscal_year") is not None
    ]
    if not cands:
        cands = [s for s in silver_mapped if s.get("fiscal_year") is not None]
    if not cands:
        return None, None
    best = max(
        cands,
        key=lambda x: (x.get("fiscal_year") or 0, str(x.get("fiscal_period") or "")),
    )
    return best.get("fiscal_year"), best.get("fiscal_period")


def _silver_matches_primary(
    s: dict[str, Any],
    *,
    primary_fy: Optional[int],
    primary_fp: Optional[str],
) -> bool:
    if primary_fy is None:
        return False
    if s.get("fiscal_year") != primary_fy:
        return False
    canon = s.get("canonical_concept") or ""
    fp = s.get("fiscal_period")
    fp_s = str(fp).strip() if fp is not None else ""
    primary_fp_s = (primary_fp or "").strip()

    if canon in _INSTANT_CANONICALS:
        return fp_s == "" or fp_s == primary_fp_s or fp_s.upper() == primary_fp_s.upper()

    if not primary_fp_s:
        return True
    return fp_s.upper() == primary_fp_s.upper()


def build_snapshot_row(
    *,
    raw_rows: list[dict[str, Any]],
    silver_rows: list[dict[str, Any]],
    cik: str,
    accession_no: str,
    filed_at: Optional[datetime],
    accepted_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    primary fiscal 기간에 맞는 silver fact로 스냅샷 dict 생성.
    snapshot_json에 채움/누락 canonical을 기록한다.
    """
    now = now or datetime.now(timezone.utc)
    primary_fy, primary_fp = parse_primary_fiscal_from_facts(raw_rows)
    mapped_silver = [s for s in silver_rows if s.get("canonical_concept")]
    if primary_fy is None:
        primary_fy, primary_fp = _fallback_primary_fiscal(mapped_silver)
    elif primary_fp is None or str(primary_fp).strip() == "":
        _, fp2 = _fallback_primary_fiscal(mapped_silver)
        if fp2:
            primary_fp = fp2
    if primary_fy is None:
        primary_fy = -1
        primary_fp = primary_fp or "UNKNOWN"
    primary_fp = (primary_fp or "").strip() or "UNSPECIFIED"

    matched = [s for s in mapped_silver if _silver_matches_primary(s, primary_fy=primary_fy, primary_fp=primary_fp)]

    by_canon: dict[str, dict[str, Any]] = {}
    for s in matched:
        c = s.get("canonical_concept")
        if not c:
            continue
        prev = by_canon.get(c)
        if prev is None:
            by_canon[c] = s
        else:
            # 동일 canonical 다건: numeric이 있는 행 우선
            if prev.get("numeric_value") is None and s.get("numeric_value") is not None:
                by_canon[c] = s

    filled: dict[str, Any] = {}
    missing: list[str] = []
    row: dict[str, Any] = {
        "cik": cik,
        "fiscal_year": primary_fy,
        "fiscal_period": primary_fp or "",
        "period_start": None,
        "period_end": None,
        "filed_at": filed_at.isoformat() if filed_at else None,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
        "accession_no": accession_no,
        "revenue": None,
        "net_income": None,
        "operating_cash_flow": None,
        "total_assets": None,
        "total_liabilities": None,
        "cash_and_equivalents": None,
        "research_and_development": None,
        "capex": None,
        "gross_profit": None,
        "shares_outstanding": None,
        "snapshot_json": {},
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    for canon, col in CANONICAL_TO_SNAPSHOT_COL.items():
        src = by_canon.get(canon)
        if src and src.get("numeric_value") is not None:
            row[col] = src.get("numeric_value")
            filled[canon] = {
                "source_concept": src.get("source_concept"),
                "fact_period_key": src.get("fact_period_key"),
            }
        else:
            missing.append(canon)

    ps, pe = _coerce_period_dates(matched)
    row["period_start"] = ps.isoformat() if ps else None
    row["period_end"] = pe.isoformat() if pe else None

    row["snapshot_json"] = {
        "primary_fiscal_year": primary_fy,
        "primary_fiscal_period": primary_fp,
        "filled_canonicals": filled,
        "missing_canonicals": missing,
        "accession_no": accession_no,
    }
    return row
