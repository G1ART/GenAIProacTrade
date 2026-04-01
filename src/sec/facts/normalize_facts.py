"""
XBRL fact 행 정규화: raw 행 dict / silver 행 dict, fact_period_key.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from sec.facts.concept_map import map_source_concept


def _json_safe(v: Any) -> Any:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "isoformat") and callable(v.isoformat):
        try:
            return v.isoformat()
        except (TypeError, ValueError):
            return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _to_date(v: Any) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, pd.Timestamp):
        return v.date() if not pd.isna(v) else None
    return None


def raw_dedupe_key(
    *,
    concept: str,
    context_ref: Optional[str],
    period_start: Optional[date],
    period_end: Optional[date],
    instant_date: Optional[date],
    unit_ref: Optional[str],
    value_repr: str,
) -> str:
    payload = {
        "c": concept or "",
        "ctx": context_ref or "",
        "ps": period_start.isoformat() if period_start else "",
        "pe": period_end.isoformat() if period_end else "",
        "inst": instant_date.isoformat() if instant_date else "",
        "u": unit_ref or "",
        "v": value_repr[:4000],
    }
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode()).hexdigest()


def make_fact_period_key(
    *,
    fact_type: str,
    fiscal_year: Optional[int],
    fiscal_period: Optional[str],
    period_start: Optional[date],
    period_end: Optional[date],
    instant_date: Optional[date],
) -> str:
    fy = int(fiscal_year) if fiscal_year is not None and not pd.isna(fiscal_year) else -1
    fp = (str(fiscal_period).strip() if fiscal_period is not None and not pd.isna(fiscal_period) else "") or ""
    ps = period_start.isoformat() if period_start else ""
    pe = period_end.isoformat() if period_end else ""
    inst = instant_date.isoformat() if instant_date else ""
    ft = (fact_type or "").strip().lower() or "unknown"
    return f"{fy}|{fp}|{ft}|{ps}|{pe}|{inst}"


def dataframe_row_to_raw_fact_dict(
    row: Any,
    *,
    cik: str,
    accession_no: str,
    filed_at: Optional[datetime],
    accepted_at: Optional[datetime],
) -> dict[str, Any]:
    """pandas Series 또는 dict-like."""
    def g(key: str, default=None):
        if hasattr(row, "get"):
            return row.get(key, default)
        try:
            return row[key]
        except Exception:
            return default

    concept = str(g("concept") or "")
    tax = concept.split(":")[0] if ":" in concept else None
    context_ref = g("context_ref")
    if context_ref is not None and not isinstance(context_ref, str):
        context_ref = str(context_ref)
    unit_ref = g("unit_ref")
    if unit_ref is not None and not isinstance(unit_ref, str):
        unit_ref = str(unit_ref)

    period_type = str(g("period_type") or "").lower()
    ps = _to_date(g("period_start"))
    pe = _to_date(g("period_end"))
    instant_date: Optional[date] = None
    if period_type == "instant":
        instant_date = pe or ps

    val_raw = g("value")
    num = g("numeric_value")
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    if num is not None and not (isinstance(num, float) and pd.isna(num)):
        try:
            value_numeric = float(num)
        except (TypeError, ValueError):
            value_text = str(val_raw) if val_raw is not None else None
    else:
        if val_raw is not None and not (isinstance(val_raw, float) and pd.isna(val_raw)):
            value_text = str(val_raw)

    value_repr = (
        str(value_numeric) if value_numeric is not None else (value_text or "")
    )

    fy = g("fiscal_year")
    if fy is not None and not pd.isna(fy):
        try:
            fy = int(fy)
        except (TypeError, ValueError):
            fy = None
    else:
        fy = None

    fp = g("fiscal_period")
    if fp is not None and not pd.isna(fp):
        fp = str(fp).strip()
    else:
        fp = None

    dedupe = raw_dedupe_key(
        concept=concept,
        context_ref=context_ref,
        period_start=ps,
        period_end=pe,
        instant_date=instant_date,
        unit_ref=unit_ref,
        value_repr=value_repr,
    )

    payload = {k: _json_safe(g(k)) for k in ("fact_key", "fact_id", "label", "balance", "decimals")}
    payload["context_ref"] = context_ref
    payload["unit_ref"] = unit_ref
    payload["period_type"] = period_type

    return {
        "cik": cik,
        "accession_no": accession_no,
        "dedupe_key": dedupe,
        "taxonomy": tax,
        "concept": concept,
        "unit": unit_ref,
        "value_text": value_text,
        "value_numeric": value_numeric,
        "period_start": ps.isoformat() if ps else None,
        "period_end": pe.isoformat() if pe else None,
        "instant_date": instant_date.isoformat() if instant_date else None,
        "fiscal_year": fy,
        "fiscal_period": fp,
        "filed_at": filed_at.isoformat() if filed_at else None,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
        "source_payload_json": payload,
    }


def raw_dict_to_silver_candidate(raw: dict[str, Any], *, revision_no: int = 1) -> Optional[dict[str, Any]]:
    """매핑되는 raw만 silver 행 후보 생성."""
    concept = raw.get("concept") or ""
    canonical, status = map_source_concept(concept)
    if status != "mapped" or not canonical:
        return None

    period_start = date.fromisoformat(raw["period_start"]) if raw.get("period_start") else None
    period_end = date.fromisoformat(raw["period_end"]) if raw.get("period_end") else None
    instant_date = date.fromisoformat(raw["instant_date"]) if raw.get("instant_date") else None
    spi = raw.get("source_payload_json") or {}
    pt = str(spi.get("period_type") or "").lower()
    if pt == "instant":
        fact_type = "instant"
    elif pt == "duration":
        fact_type = "duration"
    elif raw.get("instant_date"):
        fact_type = "instant"
    else:
        fact_type = "duration"

    fpk = make_fact_period_key(
        fact_type=fact_type,
        fiscal_year=raw.get("fiscal_year"),
        fiscal_period=raw.get("fiscal_period"),
        period_start=period_start,
        period_end=period_end,
        instant_date=instant_date,
    )

    num = raw.get("value_numeric")
    summary = {
        "source_concept": concept,
        "canonical": canonical,
        "dedupe_key": raw.get("dedupe_key"),
        "mapping_status": "mapped",
    }

    return {
        "cik": raw["cik"],
        "accession_no": raw["accession_no"],
        "canonical_concept": canonical,
        "source_taxonomy": raw.get("taxonomy"),
        "source_concept": concept,
        "unit": raw.get("unit"),
        "numeric_value": num,
        "period_start": raw.get("period_start"),
        "period_end": raw.get("period_end"),
        "instant_date": raw.get("instant_date"),
        "fact_type": fact_type,
        "fiscal_year": raw.get("fiscal_year"),
        "fiscal_period": raw.get("fiscal_period"),
        "revision_no": revision_no,
        "fact_period_key": fpk,
        "normalized_summary_json": summary,
    }


def parse_primary_fiscal_from_facts(raw_rows: list[dict[str, Any]]) -> tuple[Optional[int], Optional[str]]:
    """DEI DocumentFiscalYearFocus / DocumentFiscalPeriodFocus."""
    fy: Optional[int] = None
    fp: Optional[str] = None
    for r in raw_rows:
        c = r.get("concept") or ""
        if c == "dei:DocumentFiscalYearFocus":
            v = r.get("value_numeric")
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                try:
                    fy = int(v)
                except (TypeError, ValueError):
                    pass
            if fy is None and r.get("value_text"):
                try:
                    fy = int(float(str(r["value_text"]).strip()))
                except ValueError:
                    try:
                        fy = int(str(r["value_text"]).strip().split(".")[0])
                    except ValueError:
                        pass
        elif c == "dei:DocumentFiscalPeriodFocus":
            if r.get("value_text"):
                fp = str(r["value_text"]).strip()
            elif r.get("value_numeric") is not None and not (
                isinstance(r["value_numeric"], float) and pd.isna(r["value_numeric"])
            ):
                try:
                    fp = str(int(r["value_numeric"]))
                except (TypeError, ValueError):
                    fp = str(r["value_numeric"])
    return fy, fp
